from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from enterprise import __version__
from enterprise.agent.quote_planner import plan_quote
from enterprise.approval.models import DEFAULT_TIMEOUTS, ApprovalRequestModel, generate_approval_id
from enterprise.approval.policy import policy_snapshot, resolve_approval_route
from enterprise.approval.risk_detector import RiskAssessment, RiskContext, detect_risk
from enterprise.approval.risk_review import review_risk
from enterprise.audit.logger import write_audit_log
from enterprise.audit.models import ActionType
from enterprise.audit.sanitizer import sanitize_input
from enterprise.auth.dependencies import CurrentUser, require_any_operator
from enterprise.auth.enums import PROCUREMENT_ROLE_MAP
from enterprise.auth.models import DepartmentModel, TaskExtensionModel
from enterprise.auth.schemas import UserContext
from enterprise.llm.human_intervention import ResolutionAction
from enterprise.llm.resilient_caller import clean_llm_response
from enterprise.notification.dispatcher import notify_approval_created
from enterprise.notification.templates import ApprovalNotificationContext
from enterprise.procurement.comparison import (
    IncomparableQuotesError,
    compare_quotes,
    normalize_money,
    normalize_quantity,
)
from enterprise.procurement.models import (
    HumanReviewStatus,
    ProcurementCategoryModel,
    ProcurementHumanReviewModel,
    SupplierQuoteModel,
    generate_human_review_id,
    generate_supplier_quote_id,
)
from enterprise.procurement.quote_state import (
    advance_quote_state,
    load_quote_state,
    quote_state_response,
    save_quote_plan,
)
from enterprise.tenant.context import tenant_context_for
from enterprise.tenant.query_filter import apply_tenant_filter, filter_task_extensions
from skyvern.config import is_development_environment, settings
from skyvern.forge import app as forge_app
from skyvern.forge.sdk.db.models import ArtifactModel, TaskModel
from skyvern.forge.sdk.executor.factory import AsyncExecutorFactory
from skyvern.forge.sdk.schemas.tasks import Task, TaskRequest, TaskStatus
from skyvern.services import task_v1_service

router = APIRouter(prefix="/enterprise/procurement", tags=["enterprise-procurement"])
logger = logging.getLogger(__name__)

QUOTE_EXTRACTION_SCHEMA: dict[str, Any] = {
    "x-skyvern-preserve-missing": True,
    "type": "object",
    "properties": {
        "supplier_id": {"type": "string"},
        "material_name": {"type": "string"},
        "quantity": {"type": "number"},
        "unit": {"type": "string", "enum": ["unit"]},
        "currency": {"type": "string", "enum": ["CNY"]},
        "unit_price_cny": {"type": "number"},
        "freight_cny": {"type": "number"},
        "moq": {"type": "number"},
        "delivery_days": {"type": "integer"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "supplier_id",
        "material_name",
        "quantity",
        "unit",
        "currency",
        "unit_price_cny",
        "freight_cny",
        "moq",
        "delivery_days",
    ],
}
_QUOTE_NAVIGATION_GOAL = "Open the supplier quote page, read its single quote table, and complete the task."
_QUOTE_EXTRACTION_GOAL = (
    "Extract exactly one supplier quote from the visible quote table. Return supplier_id, material_name, quantity, "
    "unit, currency, unit_price_cny, freight_cny, moq, delivery_days, and an optional confidence from 0 to 1."
)


@router.get("/context-options")
async def context_options(user: CurrentUser) -> dict:
    """Return only the logged-in organization procurement context."""
    scope = tenant_context_for(user)
    async with forge_app.DATABASE.Session() as session:
        department_query = (
            select(DepartmentModel.department_id, DepartmentModel.department_name, DepartmentModel.department_code)
            .where(DepartmentModel.organization_id == user.org_id)
            .order_by(DepartmentModel.department_name)
        )
        category_query = (
            select(ProcurementCategoryModel.category_id, ProcurementCategoryModel.category_name, ProcurementCategoryModel.category_code)
            .where(ProcurementCategoryModel.organization_id == user.org_id)
            .order_by(ProcurementCategoryModel.category_name)
        )
        if not scope.has_full_org_visibility:
            department_query = department_query.where(
                DepartmentModel.department_id.in_(scope.visible_department_ids)
            )
            category_query = category_query.where(
                ProcurementCategoryModel.category_id.in_(scope.visible_category_ids)
            )
        departments = (await session.execute(department_query)).all()
        categories = (await session.execute(category_query)).all()
    return {
        "departments": [{"department_id": row.department_id, "name": row.department_name, "code": row.department_code} for row in departments],
        "categories": [{"category_id": row.category_id, "name": row.category_name, "code": row.category_code} for row in categories],
        "roles": [{"role": role, "procurement_role": procurement_role} for role, procurement_role in PROCUREMENT_ROLE_MAP.items()],
    }


def _task_response(extension: TaskExtensionModel, task: TaskModel) -> dict:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status,
        "organization_id": extension.organization_id,
        "department_id": extension.department_id,
        "category_id": extension.category_id,
        "risk_level": extension.risk_level,
        "risk_reason": extension.risk_reason,
        "risk_result": extension.risk_result,
        "created_by": extension.created_by,
    }


@router.get("/tasks")
async def list_procurement_tasks(user: CurrentUser) -> dict:
    """List only core tasks whose procurement context matches the caller's scope."""
    query = filter_task_extensions(
        select(TaskExtensionModel, TaskModel).join(
            TaskModel,
            (TaskModel.task_id == TaskExtensionModel.task_id)
            & (TaskModel.organization_id == TaskExtensionModel.organization_id),
        ),
        tenant_context_for(user),
    ).order_by(TaskExtensionModel.created_at.desc())
    async with forge_app.DATABASE.Session() as session:
        rows = (await session.execute(query)).all()
    return {"tasks": [_task_response(extension, task) for extension, task in rows], "total": len(rows)}


@router.get("/tasks/{task_id}")
async def get_procurement_task(task_id: str, user: CurrentUser) -> dict:
    """Return a task only after its procurement scope has been enforced."""
    query = filter_task_extensions(
        select(TaskExtensionModel, TaskModel)
        .join(
            TaskModel,
            (TaskModel.task_id == TaskExtensionModel.task_id)
            & (TaskModel.organization_id == TaskExtensionModel.organization_id),
        )
        .where(TaskExtensionModel.task_id == task_id),
        tenant_context_for(user),
    )
    async with forge_app.DATABASE.Session() as session:
        row = (await session.execute(query)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procurement task not found")
    return _task_response(*row)


class QuoteCreateRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=128)
    department_id: str = Field(min_length=1, max_length=128)
    category_id: str = Field(min_length=1, max_length=128)
    supplier_id: str = Field(min_length=1, max_length=128)
    material_name: str = Field(min_length=1, max_length=256)
    quantity: Decimal = Field(gt=0)
    unit: Literal["unit"] = "unit"
    currency: Literal["CNY"] = "CNY"
    unit_price_cny: Decimal = Field(ge=0)
    freight_cny: Decimal = Field(default=Decimal("0"), ge=0)
    moq: Decimal = Field(default=Decimal("0"), ge=0)
    delivery_days: int = Field(ge=0, le=3650)
    artifact_id: str = Field(min_length=1, max_length=128)


class ExtractedSupplierQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    supplier_id: str = Field(min_length=1, max_length=128)
    material_name: str = Field(min_length=1, max_length=256)
    quantity: Decimal = Field(gt=0)
    unit: Literal["unit"]
    currency: Literal["CNY"]
    unit_price_cny: Decimal = Field(ge=0)
    freight_cny: Decimal = Field(ge=0)
    moq: Decimal = Field(ge=0)
    delivery_days: int = Field(ge=0, le=3650)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_unit(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class ManualQuoteResult(BaseModel):
    """Validated quote fields accepted from an authorized human operator."""

    supplier_id: str = Field(min_length=1, max_length=128)
    material_name: str = Field(min_length=1, max_length=256)
    quantity: Decimal = Field(gt=0)
    unit: Literal["unit"]
    currency: Literal["CNY"]
    unit_price_cny: Decimal = Field(ge=0)
    freight_cny: Decimal = Field(default=Decimal("0"), ge=0)
    moq: Decimal = Field(default=Decimal("0"), ge=0)
    delivery_days: int = Field(ge=0, le=3650)
    artifact_id: str | None = Field(default=None, min_length=1, max_length=128)


class HumanReviewResolutionRequest(BaseModel):
    action: ResolutionAction
    note: str = Field(default="", max_length=2000)
    manual_result: ManualQuoteResult | None = None


class HumanReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: str
    task_id: str
    organization_id: str
    department_id: str
    category_id: str
    status: str
    reason_code: str
    safe_error_summary: str
    artifact_id: str | None
    action_index: int
    action_type: str
    created_by: str
    created_at: datetime.datetime
    resolved_by: str | None
    resolution_action: str | None
    resolution_note: str | None
    resolved_at: datetime.datetime | None


class HumanReviewListResponse(BaseModel):
    reviews: list[HumanReviewResponse]
    total: int


class HumanReviewResolutionResponse(HumanReviewResponse):
    quote_id: str | None = None
    task_status: str | None = None


class QuoteResponse(BaseModel):
    quote_id: str
    task_id: str
    organization_id: str
    department_id: str
    category_id: str
    supplier_id: str
    material_name: str
    quantity: str
    unit: Literal["unit"]
    currency: Literal["CNY"]
    unit_price_cny: str
    freight_cny: str
    moq: str
    delivery_days: int
    artifact_id: str
    created_by: str


class QuoteListResponse(BaseModel):
    quotes: list[QuoteResponse]
    total: int


class QuoteComparisonItemResponse(BaseModel):
    task_id: str
    artifact_id: str
    quote_id: str
    supplier_id: str
    total_cny: str
    landed_unit_price_cny: str
    delivery_days: int
    eligible: bool
    rank: int | None
    reason: str


class QuoteComparisonResponse(BaseModel):
    task_id: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    quotes: list[QuoteComparisonItemResponse]
    recommended_quote_id: str | None
    recommendation_reason: str


def _quote_response(quote: SupplierQuoteModel) -> QuoteResponse:
    return QuoteResponse(
        quote_id=quote.quote_id,
        task_id=quote.task_id,
        organization_id=quote.organization_id,
        department_id=quote.department_id,
        category_id=quote.category_id,
        supplier_id=quote.supplier_id,
        material_name=quote.material_name,
        quantity=str(normalize_quantity(quote.quantity)),
        unit=quote.unit,
        currency=quote.currency,
        unit_price_cny=str(normalize_money(quote.unit_price_cny)),
        freight_cny=str(normalize_money(quote.freight_cny)),
        moq=str(normalize_quantity(quote.moq)),
        delivery_days=quote.delivery_days,
        artifact_id=quote.artifact_id,
        created_by=quote.created_by,
    )


def _quote_query(
    user: UserContext,
    *,
    task_id: str | None = None,
    task_ids: list[str] | None = None,
    quote_id: str | None = None,
):
    query = apply_tenant_filter(select(SupplierQuoteModel), SupplierQuoteModel, tenant_context_for(user))
    query = query.join(
        TaskModel,
        (TaskModel.task_id == SupplierQuoteModel.task_id)
        & (TaskModel.organization_id == SupplierQuoteModel.organization_id),
    ).join(
        TaskExtensionModel,
        (TaskExtensionModel.task_id == SupplierQuoteModel.task_id)
        & (TaskExtensionModel.organization_id == SupplierQuoteModel.organization_id),
    ).join(
        ArtifactModel,
        (ArtifactModel.artifact_id == SupplierQuoteModel.artifact_id)
        & (ArtifactModel.organization_id == SupplierQuoteModel.organization_id)
        & (ArtifactModel.task_id == SupplierQuoteModel.task_id),
    )
    if task_id is not None:
        query = query.where(SupplierQuoteModel.task_id == task_id)
    if task_ids is not None:
        query = query.where(SupplierQuoteModel.task_id.in_(task_ids))
    if quote_id is not None:
        query = query.where(SupplierQuoteModel.quote_id == quote_id)
    return query.order_by(SupplierQuoteModel.quote_id)


async def _validate_quote_context(
    session,
    payload: QuoteCreateRequest,
    user: UserContext,
) -> None:
    _assert_procurement_operator(user, user.org_id, payload.department_id, payload.category_id)

    task_context = await session.scalar(
        select(TaskExtensionModel)
        .join(
            TaskModel,
            (TaskModel.task_id == TaskExtensionModel.task_id)
            & (TaskModel.organization_id == TaskExtensionModel.organization_id),
        )
        .where(
            TaskExtensionModel.task_id == payload.task_id,
            TaskExtensionModel.organization_id == user.org_id,
            TaskExtensionModel.department_id == payload.department_id,
            TaskExtensionModel.category_id == payload.category_id,
        )
    )
    if task_context is None:
        raise HTTPException(status_code=404, detail="Procurement task context not found")

    artifact = await session.scalar(
        select(ArtifactModel.artifact_id).where(
            ArtifactModel.artifact_id == payload.artifact_id,
            ArtifactModel.organization_id == user.org_id,
            ArtifactModel.task_id == payload.task_id,
            ArtifactModel.artifact_type.in_(
                ("html_scrape", "screenshot_final", "screenshot_action")
            ),
        )
    )
    if artifact is None:
        raise HTTPException(status_code=422, detail="Quote evidence artifact is not in the authenticated organization")


async def _persist_supplier_quote(
    session,
    payload: QuoteCreateRequest,
    user: UserContext,
    *,
    commit: bool = True, native_extraction: bool = False,
) -> SupplierQuoteModel:
    await _validate_quote_context(session, payload, user)
    quote = SupplierQuoteModel(
        quote_id=generate_supplier_quote_id(),
        task_id=payload.task_id,
        organization_id=user.org_id,
        department_id=payload.department_id,
        category_id=payload.category_id,
        supplier_id=payload.supplier_id,
        material_name=payload.material_name,
        quantity=normalize_quantity(payload.quantity),
        unit=payload.unit,
        currency=payload.currency,
        unit_price_cny=normalize_money(payload.unit_price_cny),
        freight_cny=normalize_money(payload.freight_cny),
        moq=normalize_quantity(payload.moq),
        delivery_days=payload.delivery_days,
        artifact_id=payload.artifact_id,
        created_by=user.user_id,
    )
    session.add(quote)
    task = await session.scalar(select(TaskModel).where(
        TaskModel.task_id == payload.task_id, TaskModel.organization_id == user.org_id,
    ))
    if task is not None and getattr(task, "data_extraction_goal", None) == _QUOTE_EXTRACTION_GOAL:
        await advance_quote_state(
            session, task_id=payload.task_id, org_id=user.org_id, department_id=payload.department_id,
            executor=user.user_id, step="completed", native_extraction=native_extraction,
        )
    if commit:
        await session.commit()
        # commit 后默认 expire_on_commit=True 会使实例属性过期；调用方在 Session 关闭后
        # 访问 quote_id/artifact_id 等属性会触发懒加载刷新而报 "not bound to a Session"。
        refresh = getattr(session, "refresh", None)
        if refresh is not None:
            await refresh(quote)
    return quote


@router.post("/quotes", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_quote(
    payload: QuoteCreateRequest,
    user: UserContext = Depends(require_any_operator),
) -> QuoteResponse:
    try:
        async with forge_app.DATABASE.Session() as session:
            quote = await _persist_supplier_quote(session, payload, user)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A quote already exists for this task") from exc
    return _quote_response(quote)


@router.get("/quotes", response_model=QuoteListResponse)
async def list_supplier_quotes(
    user: CurrentUser,
    task_id: str | None = Query(default=None, min_length=1, max_length=128),
) -> QuoteListResponse:
    async with forge_app.DATABASE.Session() as session:
        quotes = (await session.execute(_quote_query(user, task_id=task_id))).scalars().all()
    return QuoteListResponse(quotes=[_quote_response(quote) for quote in quotes], total=len(quotes))


def _comparison_response(
    quotes: list[SupplierQuoteModel],
    *,
    task_id: str | None = None,
    task_ids: list[str] | None = None,
) -> QuoteComparisonResponse:
    try:
        result = compare_quotes(quotes)
    except IncomparableQuotesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    quotes_by_id = {quote.quote_id: quote for quote in quotes}
    return QuoteComparisonResponse(
        task_id=task_id,
        task_ids=task_ids or ([task_id] if task_id else []),
        quotes=[
            QuoteComparisonItemResponse(
                task_id=quotes_by_id[item.quote_id].task_id,
                artifact_id=quotes_by_id[item.quote_id].artifact_id,
                quote_id=item.quote_id,
                supplier_id=item.supplier_id,
                total_cny=str(item.total_cny),
                landed_unit_price_cny=str(item.landed_unit_price_cny),
                delivery_days=item.delivery_days,
                eligible=item.eligible,
                rank=item.rank,
                reason=item.reason,
            )
            for item in result.quotes
        ],
        recommended_quote_id=result.recommended_quote_id,
        recommendation_reason=result.recommendation_reason,
    )


@router.get("/quotes/compare", response_model=QuoteComparisonResponse)
async def compare_supplier_quotes_for_tasks(
    user: CurrentUser,
    task_ids: list[str] = Query(..., min_length=1, max_length=128),
) -> QuoteComparisonResponse:
    task_ids = list(dict.fromkeys(task_ids))
    async with forge_app.DATABASE.Session() as session:
        quotes = (await session.execute(_quote_query(user, task_ids=task_ids))).scalars().all()
    if not quotes:
        raise HTTPException(status_code=404, detail="Supplier quotes not found")
    return _comparison_response(quotes, task_ids=task_ids)


@router.get("/quotes/compare/{task_id}", response_model=QuoteComparisonResponse)
async def compare_supplier_quotes(task_id: str, user: CurrentUser) -> QuoteComparisonResponse:
    async with forge_app.DATABASE.Session() as session:
        quotes = (await session.execute(_quote_query(user, task_id=task_id))).scalars().all()
    if not quotes:
        raise HTTPException(status_code=404, detail="Supplier quotes not found")
    return _comparison_response(quotes, task_id=task_id)


@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
async def get_supplier_quote(quote_id: str, user: CurrentUser) -> QuoteResponse:
    async with forge_app.DATABASE.Session() as session:
        quote = (await session.execute(_quote_query(user, quote_id=quote_id))).scalar_one_or_none()
    if quote is None:
        raise HTTPException(status_code=404, detail="Supplier quote not found")
    return _quote_response(quote)


_QUOTE_REVIEW_FAILURES = {
    "Quote execution was interrupted": (
        "quote_execution_interrupted", "Quote execution was interrupted; browser actions must not be replayed",
    ),
    "Skyvern task did not complete": ("task_not_completed", "Skyvern quote task did not complete"),
    "Required quote fields are missing or have invalid types": (
        "quote_schema_invalid",
        "Extracted quote fields failed server validation",
    ),
    "Skyvern extraction confidence is below 0.80": (
        "quote_confidence_low",
        "Extracted quote confidence was below the server threshold",
    ),
    "No browser evidence artifact was recorded": (
        "quote_artifact_missing",
        "No browser evidence artifact was recorded",
    ),
}


def _human_review_response(review: ProcurementHumanReviewModel) -> HumanReviewResponse:
    return HumanReviewResponse(
        review_id=review.review_id,
        task_id=review.task_id,
        organization_id=review.organization_id,
        department_id=review.department_id,
        category_id=review.category_id,
        status=review.status,
        reason_code=review.reason_code,
        safe_error_summary=review.safe_error_summary,
        artifact_id=review.artifact_id,
        action_index=review.action_index,
        action_type=review.action_type,
        created_by=review.created_by,
        created_at=review.created_at,
        resolved_by=review.resolved_by,
        resolution_action=review.resolution_action,
        resolution_note=review.resolution_note,
        resolved_at=review.resolved_at,
    )


def _human_review_query(user: UserContext, review_id: str | None = None):
    query = apply_tenant_filter(
        select(ProcurementHumanReviewModel),
        ProcurementHumanReviewModel,
        tenant_context_for(user),
    )
    if review_id is not None:
        query = query.where(ProcurementHumanReviewModel.review_id == review_id)
    return query


def _assert_procurement_operator(
    user: UserContext, organization_id: str, department_id: str, category_id: str,
) -> None:
    if organization_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-organization write access is forbidden")
    if user.is_org_admin:
        return
    if user.get_role_in_department(department_id) != "operator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator role required in the target department")
    if not user.has_procurement_category(category_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write is outside the user's procurement category")


async def _create_or_get_quote_human_review(
    task_id: str,
    payload: QuoteTaskRequest,
    user: UserContext,
    *,
    reason_code: str,
    safe_error_summary: str,
    artifact_id: str | None = None,
) -> ProcurementHumanReviewModel:
    """Create one durable review without storing extraction output or page data."""
    async with forge_app.DATABASE.Session() as session:
        pending = await session.scalar(
            select(ProcurementHumanReviewModel).where(
                ProcurementHumanReviewModel.task_id == task_id,
                ProcurementHumanReviewModel.organization_id == user.org_id,
                ProcurementHumanReviewModel.status == HumanReviewStatus.PENDING.value,
            )
        )
        if pending is not None and hasattr(pending, "review_id"):
            return pending

        context = await session.scalar(
            select(TaskExtensionModel)
            .join(
                TaskModel,
                (TaskModel.task_id == TaskExtensionModel.task_id)
                & (TaskModel.organization_id == TaskExtensionModel.organization_id),
            )
            .where(
                TaskExtensionModel.task_id == task_id,
                TaskExtensionModel.organization_id == user.org_id,
                TaskExtensionModel.department_id == payload.department_id,
                TaskExtensionModel.category_id == payload.category_id,
            )
        )
        if context is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procurement task context not found")
        if artifact_id is None and reason_code != "quote_artifact_missing":
            artifact_id = await session.scalar(
                select(ArtifactModel.artifact_id)
                .where(
                    ArtifactModel.task_id == task_id,
                    ArtifactModel.organization_id == user.org_id,
                    ArtifactModel.artifact_type.in_(
                        ("html_scrape", "screenshot_final", "screenshot_action")
                    ),
                )
                .order_by(ArtifactModel.created_at.desc())
            )

        review = ProcurementHumanReviewModel(
            review_id=generate_human_review_id(),
            task_id=task_id,
            organization_id=user.org_id,
            department_id=payload.department_id,
            category_id=payload.category_id,
            status=HumanReviewStatus.PENDING.value,
            reason_code=reason_code,
            safe_error_summary=safe_error_summary,
            artifact_id=artifact_id,
            action_index=0,
            action_type="quote_extraction",
            created_by=user.user_id,
        )
        # The task-scoped unique index is the final idempotency guard under concurrent retries.
        try:
            session.add(review)
            await advance_quote_state(
                session, task_id=task_id, org_id=user.org_id, department_id=payload.department_id,
                executor=user.user_id, step="needs_human",
            )
            await write_audit_log(session, commit=False,
                task_id=review.task_id,
                org_id=review.organization_id,
                department_id=review.department_id,
                business_object_type="procurement_human_review",
                business_object_id=review.review_id,
                action_index=review.action_index,
                action_type=ActionType.HUMAN_REVIEW_CREATED.value,
                executor=review.created_by,
                input_value={"reason_code": review.reason_code, "review_id": review.review_id},
                execution_result=HumanReviewStatus.PENDING.value,
                error_message=review.safe_error_summary,
            )
            await session.commit()
            if hasattr(session, "refresh"):
                await session.refresh(review)
        except IntegrityError:
            await session.rollback()
            pending = await session.scalar(
                select(ProcurementHumanReviewModel).where(
                    ProcurementHumanReviewModel.task_id == task_id,
                    ProcurementHumanReviewModel.organization_id == user.org_id,
                    ProcurementHumanReviewModel.status == HumanReviewStatus.PENDING.value,
                )
            )
            if pending is None:
                raise
            review = pending

    return review


async def _quote_needs_human_confirmation(
    task_id: str,
    reason: str,
    payload: QuoteTaskRequest,
    user: UserContext,
    artifact_id: str | None = None,
) -> HTTPException:
    reason_code, safe_error_summary = _QUOTE_REVIEW_FAILURES.get(
        reason,
        ("quote_validation_failed", "Quote extraction requires human review"),
    )
    try:
        review = await _create_or_get_quote_human_review(
            task_id,
            payload,
            user,
            reason_code=reason_code,
            safe_error_summary=safe_error_summary,
            artifact_id=artifact_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "HUMAN_REVIEW_PERSIST_FAILURE task=%s error_type=%s",
            task_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "human_review_persistence_failed", "task_id": task_id},
        ) from exc
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "quote_needs_human_confirmation",
            "task_id": task_id,
            "review_id": review.review_id,
            "review_status": review.status,
            "enterprise_status": "needs_human",
            "reason_code": review.reason_code,
            "reason": reason if reason in _QUOTE_REVIEW_FAILURES else review.safe_error_summary,
        },
    )


@router.get("/human-reviews", response_model=HumanReviewListResponse)
async def list_human_reviews(
    user: UserContext = Depends(require_any_operator),
    status_filter: HumanReviewStatus | None = Query(default=None, alias="status"),
) -> HumanReviewListResponse:
    query = _human_review_query(user)
    if status_filter is not None:
        query = query.where(ProcurementHumanReviewModel.status == status_filter.value)
    async with forge_app.DATABASE.Session() as session:
        reviews = (await session.scalars(query.order_by(ProcurementHumanReviewModel.created_at.desc()))).all()
    return HumanReviewListResponse(
        reviews=[_human_review_response(review) for review in reviews],
        total=len(reviews),
    )


@router.get("/human-reviews/{review_id}", response_model=HumanReviewResponse)
async def get_human_review(
    review_id: str,
    user: UserContext = Depends(require_any_operator),
) -> HumanReviewResponse:
    async with forge_app.DATABASE.Session() as session:
        review = await session.scalar(_human_review_query(user, review_id))
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Human review not found")
    return _human_review_response(review)


@router.post("/human-reviews/{review_id}/resolve", response_model=HumanReviewResolutionResponse)
async def resolve_human_review(
    review_id: str,
    body: HumanReviewResolutionRequest,
    user: UserContext = Depends(require_any_operator),
) -> HumanReviewResolutionResponse:
    if body.action is ResolutionAction.MANUAL_COMPLETE and body.manual_result is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="manual_result is required")
    if body.action is not ResolutionAction.MANUAL_COMPLETE and body.manual_result is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="manual_result is only valid for manual_complete")

    quote: SupplierQuoteModel | None = None
    task_status: str | None = None
    async with forge_app.DATABASE.Session() as session:
        review = await session.scalar(_human_review_query(user, review_id).with_for_update())
        if review is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Human review not found")
        _assert_procurement_operator(user, review.organization_id, review.department_id, review.category_id)
        if review.status != HumanReviewStatus.PENDING.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Human review is already {review.status}")

        if body.action is ResolutionAction.MANUAL_COMPLETE:
            manual = body.manual_result
            artifact_id = manual.artifact_id or review.artifact_id
            if artifact_id is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="manual_complete requires a browser evidence artifact")
            quote = await _persist_supplier_quote(
                session,
                QuoteCreateRequest(
                    task_id=review.task_id,
                    department_id=review.department_id,
                    category_id=review.category_id,
                    supplier_id=manual.supplier_id,
                    material_name=manual.material_name,
                    quantity=manual.quantity,
                    unit=manual.unit,
                    currency=manual.currency,
                    unit_price_cny=manual.unit_price_cny,
                    freight_cny=manual.freight_cny,
                    moq=manual.moq,
                    delivery_days=manual.delivery_days,
                    artifact_id=artifact_id,
                ),
                user,
                commit=False,
            )
        if body.action is ResolutionAction.TERMINATE:
            task = await session.scalar(
                select(TaskModel).where(
                    TaskModel.task_id == review.task_id,
                    TaskModel.organization_id == review.organization_id,
                )
            )
            if task is not None:
                try:
                    current_status = TaskStatus(task.status)
                except (TypeError, ValueError):
                    current_status = None
                if current_status is not None and current_status.can_update_to(TaskStatus.terminated):
                    task.status = TaskStatus.terminated
                task_status = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)

        now = datetime.datetime.utcnow()
        review.status = (
            HumanReviewStatus.TERMINATED.value
            if body.action is ResolutionAction.TERMINATE
            else HumanReviewStatus.RESOLVED.value
        )
        review.resolved_by = user.user_id
        review.resolution_action = body.action.value
        review.resolution_note = sanitize_input(body.note) or ""
        review.resolved_at = now
        if review.action_type == "quote_extraction":
            await advance_quote_state(
                session, task_id=review.task_id, org_id=user.org_id, department_id=review.department_id,
                executor=user.user_id, step={"manual_complete": "completed", "terminate": "terminated", "skip_step": "skipped"}[body.action.value],
            )
        await write_audit_log(session, commit=False,
            task_id=review.task_id,
            org_id=review.organization_id,
            department_id=review.department_id,
            business_object_type="procurement_human_review",
            business_object_id=review.review_id,
            action_index=review.action_index,
            action_type=(
                ActionType.HUMAN_REVIEW_TERMINATED.value
                if body.action is ResolutionAction.TERMINATE
                else ActionType.HUMAN_REVIEW_RESOLVED.value
            ),
            executor=user.user_id,
            input_value={"resolution_action": body.action.value, "review_id": review.review_id},
            execution_result=review.status,
            error_message=body.note or None,
        )
        await session.commit()
        if hasattr(session, "refresh"):
            await session.refresh(review)
            if quote is not None:
                await session.refresh(quote)

    response = HumanReviewResolutionResponse(**_human_review_response(review).model_dump())
    response.quote_id = quote.quote_id if quote is not None else None
    response.task_status = task_status
    return response


class ComponentHealth(BaseModel):
    status: Literal["ok", "unavailable", "not_configured"]
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: Literal["procurerpa-enterprise"]
    ready: bool
    skyvern_core: ComponentHealth
    database: ComponentHealth
    redis: ComponentHealth
    minio: ComponentHealth
    browser: ComponentHealth
    version: str


class ProcurementRiskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_amount_cny: Decimal = Field(default=Decimal("0"), ge=0)
    supplier_id: str | None = Field(default=None, max_length=128)
    is_new_supplier: bool = False
    supplier_qualified: bool | None = None
    selected_quote_cny: Decimal | None = Field(default=None, ge=0)
    average_quote_cny: Decimal | None = Field(default=None, gt=0)
    operation_type: Literal[
        "standard", "single_source", "emergency", "advance_payment", "supplier_bank_change"
    ] = "standard"
    tax_rate: Decimal | None = Field(default=None, ge=0, le=1)
    redacted_description: str | None = Field(default=None, max_length=2000)

    def to_context(self) -> RiskContext:
        return RiskContext(**self.model_dump())


class SmokeTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(min_length=1, max_length=128)
    department_id: str = Field(min_length=1, max_length=128)
    category_id: str = Field(min_length=1, max_length=128)
    url: str = Field(min_length=1, max_length=2048)
    risk: ProcurementRiskInput = Field(default_factory=ProcurementRiskInput)


class QuoteTaskRequest(SmokeTaskRequest):
    """Request for one allowlisted supplier quote extraction task."""


class SmokeTaskResponse(BaseModel):
    task_id: str
    task_status: str
    outcome: Literal["completed", "failed", "pending_approval", "rejected", "running"]
    idempotent: bool
    approval_id: str | None = None


class QuoteTaskResponse(SmokeTaskResponse):
    quote_id: str | None = None
    artifact_id: str | None = None


_SMOKE_LOCK = asyncio.Lock()
_SMOKE_PROMPT = "On the allowlisted example page, click the 'More information' link and report completion."


def _request_key_hash(kind: str, idempotency_key: str) -> str:
    return f"{kind}:{hashlib.sha256(idempotency_key.encode()).hexdigest()}"


async def _persisted_request(organization_id: str, request_key_hash: str) -> tuple[str, str | None] | None:
    async with forge_app.DATABASE.Session() as session:
        context = await session.scalar(
            select(TaskExtensionModel).where(
                TaskExtensionModel.organization_id == organization_id,
                TaskExtensionModel.request_key_hash == request_key_hash,
            )
        )
        if context is None:
            return None
        approval_id = await session.scalar(
            select(ApprovalRequestModel.approval_id).where(
                ApprovalRequestModel.task_id == context.task_id,
                ApprovalRequestModel.organization_id == organization_id,
            )
        )
    return context.task_id, approval_id


async def _cancel_orphan_task(task_id: str, organization_id: str) -> None:
    try:
        await forge_app.DATABASE.update_task(task_id, status=TaskStatus.canceled, organization_id=organization_id)
    except Exception as exc:
        logger.warning("IDEMPOTENCY_ORPHAN_CANCEL_FAILED task=%s error_type=%s", task_id, type(exc).__name__)


def _component_ok(detail: str) -> ComponentHealth:
    return ComponentHealth(status="ok", detail=detail)


def _component_unavailable(detail: str) -> ComponentHealth:
    return ComponentHealth(status="unavailable", detail=detail)


async def _check_database() -> ComponentHealth:
    try:
        async with forge_app.DATABASE.Session() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2)
        return _component_ok("database query succeeded")
    except Exception:
        return _component_unavailable("database query failed")


async def _check_redis() -> ComponentHealth:
    client: Redis | None = None
    try:
        client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        await client.ping()
        return _component_ok("redis ping succeeded")
    except Exception:
        return _component_unavailable("redis ping failed")
    finally:
        if client is not None:
            await client.aclose()


async def _check_minio() -> ComponentHealth:
    endpoint = (settings.MINIO_ENDPOINT or "").strip()
    if not endpoint:
        return ComponentHealth(status="not_configured", detail="MinIO endpoint is not configured")
    scheme = "https" if settings.MINIO_USE_SSL else "http"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{scheme}://{endpoint}/minio/health/live")
        if response.is_success:
            return _component_ok("MinIO live endpoint succeeded")
    except Exception:
        pass
    return _component_unavailable("MinIO live endpoint failed")


async def _check_browser() -> ComponentHealth:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            if Path(playwright.chromium.executable_path).is_file():
                return _component_ok("Chromium executable is installed")
    except Exception:
        pass
    return _component_unavailable("Chromium executable is unavailable")


def _check_skyvern_core() -> ComponentHealth:
    agent = getattr(forge_app, "agent", None)
    database = getattr(forge_app, "DATABASE", None)
    if agent is not None and callable(getattr(agent, "execute_step", None)) and database is not None:
        return _component_ok("ForgeAgent and database service are initialized")
    return _component_unavailable("ForgeAgent or database service is not initialized")


def _allowed_smoke_urls() -> set[str]:
    return {url.strip() for url in settings.PROCUREMENT_SMOKE_ALLOWED_URLS.split(",") if url.strip()}


async def _get_smoke_task(task_id: str, organization_id: str) -> Task:
    try:
        task = await forge_app.DATABASE.get_task(task_id, organization_id=organization_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Smoke task could not be verified because the database is unavailable") from exc
    if task is None:
        raise HTTPException(status_code=502, detail="Smoke task was not persisted by Skyvern")
    return task


async def _create_smoke_task(
    request: Request,
    organization_id: str,
    url: str,
    background_tasks: BackgroundTasks,
    defer_execution: bool,
    task_request: TaskRequest | None = None,
) -> Task:
    organization = await forge_app.DATABASE.get_organization(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization was not found")
    return await task_v1_service.run_task(
        task=task_request or TaskRequest(title="ProcureRPA Day 1 smoke task", url=url, navigation_goal=_SMOKE_PROMPT),
        organization=organization,
        request=request,
        background_tasks=background_tasks,
        defer_execution=defer_execution,
    )


async def _attach_procurement_context(
    task_id: str,
    payload: SmokeTaskRequest,
    user: UserContext,
    risk: RiskAssessment,
    request_key_hash: str | None = None,
) -> str | None:
    approval = None
    async with forge_app.DATABASE.Session() as session:
        session.add(TaskExtensionModel(
            task_id=task_id,
            organization_id=user.org_id,
            department_id=payload.department_id,
            category_id=payload.category_id,
            risk_level=risk.risk_level,
            risk_reason=risk.reason,
            risk_result=risk.to_dict(),
            request_key_hash=request_key_hash,
            created_by=user.user_id,
        ))
        if risk.risk_level in ("high", "critical"):
            route = await resolve_approval_route(
                session, org_id=user.org_id, department_id=payload.department_id,
                category_id=payload.category_id, requester_user_id=user.user_id, risk_level=risk.risk_level,
            )
            approval_id = generate_approval_id()
            approval = ApprovalRequestModel(
                approval_id=approval_id,
                task_id=task_id,
                organization_id=user.org_id,
                department_id=payload.department_id,
                requester_user_id=user.user_id,
                risk_level=risk.risk_level,
                risk_reason=risk.reason,
                operation_description=payload.risk.redacted_description,
                approver_department_id=route.approver_department_id,
                approver_role=route.approver_role,
                category_id=payload.category_id,
                **policy_snapshot(payload.risk.total_amount_cny),
                status="pending",
                timeout_seconds=DEFAULT_TIMEOUTS[risk.risk_level],
            )
            session.add(approval)
        common = {
            "task_id": task_id,
            "org_id": user.org_id,
            "department_id": payload.department_id,
            "executor": user.user_id,
        }
        await write_audit_log(session, commit=False,
            **common,
            business_object_type="procurement_task",
            business_object_id=task_id,
            action_index=0,
            action_type=ActionType.RISK_ASSESSED.value,
            input_value=risk.to_dict(),
        )
        await write_audit_log(session, commit=False,
            **common,
            business_object_type="procurement_task",
            business_object_id=task_id,
            action_index=1,
            action_type=ActionType.PROCUREMENT_SUBMITTED.value,
            input_value={"risk_level": risk.risk_level, "requires_approval": approval is not None},
            execution_result="pending_approval" if approval else "submitted",
            has_approval=approval is not None,
            approval_id=approval_id if approval else None,
        )
        if approval:
            await write_audit_log(session, commit=False,
                **common,
                business_object_type="approval",
                business_object_id=approval_id,
                action_index=2,
                action_type=ActionType.APPROVAL_REQUESTED.value,
                input_value={"risk_level": risk.risk_level, "timeout_seconds": DEFAULT_TIMEOUTS[risk.risk_level]},
                execution_result="pending",
                has_approval=True,
                approval_id=approval_id,
            )
        if isinstance(payload, QuoteTaskRequest):
            await advance_quote_state(
                session, task_id=task_id, org_id=user.org_id, department_id=payload.department_id,
                executor=user.user_id, step="awaiting_approval" if approval else "ready",
            )
        await session.commit()
    return approval_id if approval else None


async def _validate_smoke_context(payload: SmokeTaskRequest, user: UserContext) -> None:
    _assert_procurement_operator(user, payload.organization_id, payload.department_id, payload.category_id)

    async with forge_app.DATABASE.Session() as session:
        department = await session.scalar(select(DepartmentModel.department_id).where(
            DepartmentModel.department_id == payload.department_id,
            DepartmentModel.organization_id == user.org_id,
        ))
        category = await session.scalar(select(ProcurementCategoryModel.category_id).where(
            ProcurementCategoryModel.category_id == payload.category_id,
            ProcurementCategoryModel.organization_id == user.org_id,
        ))
    if department is None or category is None:
        raise HTTPException(status_code=422, detail="Smoke task department or category is not in the authenticated organization")


async def quote_continuation_payload(task: Task, user: UserContext) -> QuoteTaskRequest | None:
    """Recover quote context from persisted facts, including after a restart."""
    if (
        getattr(task, "data_extraction_goal", None) != _QUOTE_EXTRACTION_GOAL
        or getattr(task, "extracted_information_schema", None) not in (
            QUOTE_EXTRACTION_SCHEMA,
            {key: value for key, value in QUOTE_EXTRACTION_SCHEMA.items() if key != "x-skyvern-preserve-missing"},
        )
    ):
        return None
    async with forge_app.DATABASE.Session() as session:
        context = await session.scalar(select(TaskExtensionModel).where(
            TaskExtensionModel.task_id == task.task_id,
            TaskExtensionModel.organization_id == user.org_id,
        ))
    if context is None:
        raise HTTPException(status_code=404, detail="Procurement task context not found")
    _assert_procurement_operator(user, context.organization_id, context.department_id, context.category_id)
    return QuoteTaskRequest(
        organization_id=context.organization_id,
        department_id=context.department_id,
        category_id=context.category_id,
        url=task.url,
    )


async def recover_quote_task(task_id: str, user: UserContext, expected_version: int | None = None) -> SupplierQuoteModel:
    """Serialize initial execution and explicit recovery across API processes."""
    task = await _get_smoke_task(task_id, user.org_id)
    payload = await quote_continuation_payload(task, user)
    if payload is None:
        raise HTTPException(status_code=409, detail="Task is not a procurement quote task")
    # ponytail: one DB connection held per execution; use fenced leases only if pool pressure warrants it.
    async with forge_app.DATABASE.Session() as claim:
        context = await claim.scalar(select(TaskExtensionModel).where(
            TaskExtensionModel.task_id == task_id,
            TaskExtensionModel.organization_id == user.org_id,
        ).with_for_update(skip_locked=True))
        if context is None:
            raise HTTPException(status_code=409, detail="Quote task is already being executed or recovered")
        _assert_procurement_operator(user, context.organization_id, context.department_id, context.category_id)
        approval = await claim.scalar(select(ApprovalRequestModel).where(
            ApprovalRequestModel.task_id == task_id,
            ApprovalRequestModel.organization_id == user.org_id,
        ))
        if approval is not None:
            if approval.requester_user_id != user.user_id and not user.is_org_admin:
                raise HTTPException(status_code=403, detail="Only the requester can continue this task")
            if approval.status != "approved":
                raise HTTPException(status_code=409, detail="Only approved tasks can continue")
        elif context.risk_level in ("high", "critical"):
            raise HTTPException(status_code=409, detail="Quote approval is unavailable")

        if expected_version is not None:
            state = await load_quote_state(claim, task_id, user.org_id)
            if expected_version != (state.version if state is not None else 0):
                raise HTTPException(409, "Quote state version conflict")
        existing = await claim.scalar(_quote_query(user, task_id=task_id))
        if existing is not None:
            return existing
        review = await claim.scalar(select(ProcurementHumanReviewModel).where(
            ProcurementHumanReviewModel.task_id == task_id,
            ProcurementHumanReviewModel.organization_id == user.org_id,
        ))
        if review is not None:
            raise HTTPException(status_code=409, detail={
                "code": "quote_recovery_requires_human", "review_id": review.review_id,
                "review_status": review.status, "enterprise_status": "needs_human",
            })
        task = await _get_smoke_task(task_id, user.org_id)
        if task.status not in (TaskStatus.created, TaskStatus.completed):
            raise await _quote_needs_human_confirmation(
                task_id, "Quote execution was interrupted", payload, user,
            )
        async with forge_app.DATABASE.Session() as session:
            state = await load_quote_state(session, task_id, user.org_id)
            plan = await plan_quote(
                native_completed=task.status == TaskStatus.completed,
                previous=state.current_plan.get("orchestration") if state is not None else None,
            )
            await save_quote_plan(
                session, task_id=task_id, org_id=user.org_id, department_id=payload.department_id,
                executor=user.user_id, plan=plan,
            )
            await session.commit()
        if "execute_native" in plan["steps"]:
            # Commit native uncertainty marker, enterprise step and audit before browser side effects.
            async with forge_app.DATABASE.Session() as session:
                native = await session.scalar(select(TaskModel).where(
                    TaskModel.task_id == task_id, TaskModel.organization_id == user.org_id,
                ).with_for_update())
                if native is None or native.status != TaskStatus.created:
                    raise HTTPException(409, "Quote task state changed")
                native.status = TaskStatus.running
                await advance_quote_state(
                    session, task_id=task_id, org_id=user.org_id, department_id=payload.department_id,
                    executor=user.user_id, step="running",
                )
                await write_audit_log(session, commit=False,
                    task_id=task_id, org_id=user.org_id, department_id=payload.department_id,
                    business_object_type="approval" if approval else "procurement_task",
                    business_object_id=approval.approval_id if approval else task_id,
                    action_index=5, action_type=ActionType.TASK_CONTINUED.value,
                    executor=user.user_id, execution_result="running",
                    has_approval=approval is not None,
                    approval_id=approval.approval_id if approval else None,
                    approver_user_id=approval.approver_user_id if approval else None,
                )
                await session.commit()
            execution_tasks = BackgroundTasks()
            try:
                await AsyncExecutorFactory.get_executor().execute_task(
                    request=None, background_tasks=execution_tasks, task_id=task_id,
                    organization_id=user.org_id, max_steps_override=None,
                    browser_session_id=task.browser_session_id, api_key=None,
                )
                await execution_tasks()
            except Exception:
                raise await _quote_needs_human_confirmation(
                    task_id, "Quote execution was interrupted", payload, user,
                ) from None
            task = await _get_smoke_task(task_id, user.org_id)
        if task.status != TaskStatus.completed:
            raise await _quote_needs_human_confirmation(
                task_id, "Quote execution was interrupted", payload, user,
            )
        return await _persist_extracted_quote(task, payload, user)


@router.get("/tasks/{task_id}/quote-state")
async def get_quote_state(task_id: str, user: CurrentUser) -> dict:
    await get_procurement_task(task_id, user)
    async with forge_app.DATABASE.Session() as session:
        row = await load_quote_state(session, task_id, user.org_id)
        return {"state": quote_state_response(row)}


@router.post("/tasks/{task_id}/recover-quote", response_model=QuoteResponse)
async def recover_quote(
    task_id: str, user: UserContext = Depends(require_any_operator), expected_version: int | None = None,
) -> QuoteResponse:
    return _quote_response(await recover_quote_task(task_id, user, expected_version))


async def _persist_extracted_quote(
    task: Task,
    payload: QuoteTaskRequest,
    user: UserContext,
) -> SupplierQuoteModel:
    if task.status != TaskStatus.completed:
        raise await _quote_needs_human_confirmation(task.task_id, "Skyvern task did not complete", payload, user)
    async with forge_app.DATABASE.Session() as session:
        existing = await session.scalar(
            select(SupplierQuoteModel).where(
                SupplierQuoteModel.task_id == task.task_id,
                SupplierQuoteModel.organization_id == user.org_id,
            )
        )
    if existing is not None:
        return existing
    try:
        information = task.extracted_information
        if isinstance(information, str):
            information = json.loads(clean_llm_response(information), parse_float=Decimal)
        extracted = ExtractedSupplierQuote.model_validate(information)
    except (ValidationError, json.JSONDecodeError):
        raise await _quote_needs_human_confirmation(
            task.task_id,
            "Required quote fields are missing or have invalid types",
            payload,
            user,
        ) from None
    if extracted.confidence is not None and extracted.confidence < Decimal("0.80"):
        raise await _quote_needs_human_confirmation(
            task.task_id,
            "Skyvern extraction confidence is below 0.80",
            payload,
            user,
        )

    async with forge_app.DATABASE.Session() as session:
        artifact_id = await session.scalar(
            select(ArtifactModel.artifact_id)
            .where(
                ArtifactModel.task_id == task.task_id,
                ArtifactModel.organization_id == user.org_id,
                ArtifactModel.artifact_type.in_(
                    ("html_scrape", "screenshot_final", "screenshot_action")
                ),
            )
            .order_by(ArtifactModel.created_at.desc())
        )
        if artifact_id is None:
            raise await _quote_needs_human_confirmation(
                task.task_id,
                "No browser evidence artifact was recorded",
                payload,
                user,
            )
        try:
            quote = await _persist_supplier_quote(
                session,
                QuoteCreateRequest(
                    task_id=task.task_id,
                    department_id=payload.department_id,
                    category_id=payload.category_id,
                    supplier_id=extracted.supplier_id,
                    material_name=extracted.material_name,
                    quantity=extracted.quantity,
                    unit=extracted.unit,
                    currency=extracted.currency,
                    unit_price_cny=extracted.unit_price_cny,
                    freight_cny=extracted.freight_cny,
                    moq=extracted.moq,
                    delivery_days=extracted.delivery_days,
                    artifact_id=artifact_id,
                ),
                user, native_extraction=True,
            )
        except IntegrityError:
            await session.rollback()
            quote = await session.scalar(
                select(SupplierQuoteModel).where(
                    SupplierQuoteModel.task_id == task.task_id,
                    SupplierQuoteModel.organization_id == user.org_id,
                )
            )
            if quote is None:
                raise
    return quote


def _schedule_approval_notification(
    background_tasks: BackgroundTasks,
    approval_id: str,
    task_id: str,
    risk: RiskAssessment,
    payload: SmokeTaskRequest,
    user: UserContext,
) -> None:
    department_name = next(
        (
            role.department_name
            for role in user.department_roles
            if role.department_id == payload.department_id
        ),
        payload.department_id,
    )
    background_tasks.add_task(
        notify_approval_created,
        ApprovalNotificationContext(
            approval_id=approval_id,
            task_id=task_id,
            risk_level=risk.risk_level,
            department_name=department_name,
            approval_url=settings.PROCUREMENT_APPROVAL_URL,
            timeout_seconds=DEFAULT_TIMEOUTS[risk.risk_level],
            organization_id=user.org_id,
            department_id=payload.department_id,
        ),
    )


def _smoke_response(
    task: Task,
    idempotent: bool,
    response: Response,
    approval_id: str | None = None,
) -> SmokeTaskResponse:
    task_status = str(task.status)
    if approval_id and task_status == TaskStatus.created:
        response.status_code = status.HTTP_202_ACCEPTED
        outcome = "pending_approval"
    elif task_status in (TaskStatus.queued, TaskStatus.running):
        response.status_code = status.HTTP_202_ACCEPTED
        outcome = "running"
    elif task_status == TaskStatus.completed:
        outcome = "completed"
    elif task_status == TaskStatus.canceled and approval_id:
        response.status_code = status.HTTP_409_CONFLICT
        outcome = "rejected"
    else:
        response.status_code = status.HTTP_502_BAD_GATEWAY
        outcome = "failed"
    return SmokeTaskResponse(
        task_id=task.task_id,
        task_status=task_status,
        outcome=outcome,
        idempotent=idempotent,
        approval_id=approval_id,
    )


@router.get("/health", response_model=HealthResponse)
async def health(response: Response, ready: bool = False) -> HealthResponse:
    core, database, redis, minio, browser = await asyncio.gather(
        asyncio.to_thread(_check_skyvern_core),
        _check_database(),
        _check_redis(),
        _check_minio(),
        _check_browser(),
    )
    is_ready = all(component.status == "ok" for component in (core, database, redis, minio, browser))
    if ready and not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if is_ready and minio.status == "ok" else "degraded",
        service="procurerpa-enterprise",
        ready=is_ready,
        skyvern_core=core,
        database=database,
        redis=redis,
        minio=minio,
        browser=browser,
        version=__version__,
    )


@router.post("/smoke-task", response_model=SmokeTaskResponse)
async def smoke_task(
    payload: SmokeTaskRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
    user: UserContext = Depends(require_any_operator),
) -> SmokeTaskResponse:
    if not is_development_environment(settings.ENV):
        raise HTTPException(status_code=404, detail="Smoke task is disabled outside development")
    if payload.organization_id != user.org_id:
        raise HTTPException(status_code=403, detail="Smoke task organization must match the authenticated organization")
    if payload.url not in _allowed_smoke_urls():
        raise HTTPException(status_code=400, detail="Smoke task URL is not allowlisted")
    await _validate_smoke_context(payload, user)

    request_key_hash = _request_key_hash("smoke", idempotency_key)
    async with _SMOKE_LOCK:
        if stored := await _persisted_request(payload.organization_id, request_key_hash):
            task_id, approval_id = stored
            return _smoke_response(
                await _get_smoke_task(task_id, payload.organization_id),
                True,
                response,
                approval_id,
            )

        risk = await detect_risk(payload.risk.to_context())
        requires_approval = risk.risk_level in ("high", "critical")
        execution_tasks = BackgroundTasks()
        try:
            created_task = await _create_smoke_task(
                request=request,
                organization_id=payload.organization_id,
                url=payload.url,
                background_tasks=execution_tasks,
                defer_execution=requires_approval,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Smoke task could not be created by Skyvern") from exc

        try:
            approval_id = await _attach_procurement_context(
                created_task.task_id, payload, user, risk, request_key_hash,
            )
        except IntegrityError as exc:
            stored = await _persisted_request(payload.organization_id, request_key_hash)
            if stored is None:
                raise HTTPException(status_code=503, detail="Smoke task idempotency could not be resolved") from exc
            await _cancel_orphan_task(created_task.task_id, payload.organization_id)
            task_id, approval_id = stored
            return _smoke_response(
                await _get_smoke_task(task_id, payload.organization_id),
                True,
                response,
                approval_id,
            )
        except HTTPException:
            await _cancel_orphan_task(created_task.task_id, payload.organization_id)
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Smoke task procurement context could not be saved") from exc

        if approval_id:
            _schedule_approval_notification(background_tasks, approval_id, created_task.task_id, risk, payload, user)
            return _smoke_response(created_task, False, response, approval_id)
        try:
            await execution_tasks()
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Smoke task execution failed") from exc

        return _smoke_response(await _get_smoke_task(created_task.task_id, payload.organization_id), False, response)


def _quote_task_response(
    task: Task,
    idempotent: bool,
    response: Response,
    approval_id: str | None = None,
    quote_id: str | None = None,
    artifact_id: str | None = None,
) -> QuoteTaskResponse:
    return QuoteTaskResponse(
        **_smoke_response(task, idempotent, response, approval_id).model_dump(),
        quote_id=quote_id,
        artifact_id=artifact_id,
    )


@router.post("/quote-task", response_model=QuoteTaskResponse)
async def quote_task(
    payload: QuoteTaskRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
    user: UserContext = Depends(require_any_operator),
) -> QuoteTaskResponse:
    if not is_development_environment(settings.ENV):
        raise HTTPException(status_code=404, detail="Quote task is disabled outside development")
    if payload.organization_id != user.org_id:
        raise HTTPException(status_code=403, detail="Quote task organization must match the authenticated organization")
    if payload.url not in _allowed_smoke_urls():
        raise HTTPException(status_code=400, detail="Quote task URL is not allowlisted")
    await _validate_smoke_context(payload, user)

    request_key_hash = _request_key_hash("quote", idempotency_key)
    async with _SMOKE_LOCK:
        if stored := await _persisted_request(payload.organization_id, request_key_hash):
            task_id, approval_id = stored
            await get_procurement_task(task_id, user)
            async with forge_app.DATABASE.Session() as session:
                quote = await session.scalar(_quote_query(user, task_id=task_id))
            task = await _get_smoke_task(task_id, payload.organization_id)
            if quote is None and not (approval_id and task.status == TaskStatus.created):
                quote = await recover_quote_task(task_id, user)
                task = await _get_smoke_task(task_id, payload.organization_id)
            return _quote_task_response(
                task,
                True,
                response,
                approval_id,
                quote.quote_id if quote is not None else None,
                quote.artifact_id if quote is not None else None,
            )

        risk = await detect_risk(payload.risk.to_context(), review_risk, structured_only=True)
        task_request = TaskRequest(
            title="ProcureRPA Day 11 supplier quote",
            model={"procurement_routing": "runtime-v1"},
            url=payload.url,
            navigation_goal=_QUOTE_NAVIGATION_GOAL,
            data_extraction_goal=_QUOTE_EXTRACTION_GOAL,
            extracted_information_schema=QUOTE_EXTRACTION_SCHEMA,
        )
        try:
            created_task = await _create_smoke_task(
                request=request,
                organization_id=payload.organization_id,
                url=payload.url,
                background_tasks=BackgroundTasks(),
                defer_execution=True,
                task_request=task_request,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Quote task could not be created by Skyvern") from exc

        try:
            approval_id = await _attach_procurement_context(
                created_task.task_id, payload, user, risk, request_key_hash,
            )
        except IntegrityError as exc:
            stored = await _persisted_request(payload.organization_id, request_key_hash)
            if stored is None:
                raise HTTPException(status_code=503, detail="Quote task idempotency could not be resolved") from exc
            await _cancel_orphan_task(created_task.task_id, payload.organization_id)
            task_id, approval_id = stored
            async with forge_app.DATABASE.Session() as session:
                quote = await session.scalar(_quote_query(user, task_id=task_id))
            return _quote_task_response(
                await _get_smoke_task(task_id, payload.organization_id),
                True,
                response,
                approval_id,
                quote.quote_id if quote is not None else None,
                quote.artifact_id if quote is not None else None,
            )
        except HTTPException:
            await _cancel_orphan_task(created_task.task_id, payload.organization_id)
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Quote task procurement context could not be saved") from exc

        if approval_id:
            _schedule_approval_notification(background_tasks, approval_id, created_task.task_id, risk, payload, user)
            return _quote_task_response(created_task, False, response, approval_id)

        try:
            quote = await recover_quote_task(created_task.task_id, user)
            completed_task = await _get_smoke_task(created_task.task_id, payload.organization_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Extracted supplier quote could not be saved") from exc

        return _quote_task_response(
            completed_task,
            False,
            response,
            quote_id=quote.quote_id,
            artifact_id=quote.artifact_id,
        )
