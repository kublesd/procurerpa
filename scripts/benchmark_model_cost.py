"""Fixed, offline routing manifest and paired numeric cost comparison; no provider calls.

Run: python scripts/benchmark_model_cost.py [--measurements numeric_records.json]
Measurements must cover every fixed case, in order, with baseline/optimized cost
strings (USD) or null and success booleans. Supplied records are reported evidence,
not independently verified billing. No prices, prompts, DOM, URLs or secrets accepted.
"""

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enterprise.llm.model_router import PageFeatures, route_model, safe_feature_summary

CASES = (
    ("simple-100", PageFeatures(element_count=100)),
    ("moderate-101", PageFeatures(element_count=101)),
    ("complex-501", PageFeatures(element_count=501)),
    ("iframe-2", PageFeatures(element_count=80, has_iframe=True, iframe_depth=2)),
    ("form-20", PageFeatures(element_count=80, form_field_count=20)),
    ("shadow", PageFeatures(element_count=80, has_shadow_dom=True)),
)


def compare_costs(records=None):
    manifest = [
        {"case_id": case_id, "features": safe_feature_summary(features),
         "selected_tier": route_model(features).model_tier.value}
        for case_id, features in CASES
    ]
    result = {"sample_version": "model-cost-v1", "cases": manifest,
              "data_source": "synthetic_manifest", "cost_status": "unknown",
              "baseline_cost_usd": None, "optimized_cost_usd": None, "savings_percent": None}
    if records is None:
        return result
    if not isinstance(records, list) or len(records) != len(CASES):
        raise ValueError("Fixed sample coverage required")
    totals = {"baseline": Decimal(0), "optimized": Decimal(0)}
    unknown = False
    for (case_id, _), record in zip(CASES, records):
        if not isinstance(record, dict) or set(record) != {"case_id", "baseline", "optimized"} or record["case_id"] != case_id:
            raise ValueError("Fixed sample order and numeric fields required")
        for variant in totals:
            measurement = record[variant]
            if not isinstance(measurement, dict) or set(measurement) != {"cost_usd", "success"} or type(measurement["success"]) is not bool:
                raise ValueError("Cost and outcome fields required")
            if not measurement["success"]:
                unknown = True  # A cheaper failed run is not equivalent work.
            raw = measurement["cost_usd"]
            if raw is None:
                unknown = True
                continue
            if not isinstance(raw, str):
                raise ValueError("Cost must be a decimal string or null")
            try:
                amount = Decimal(raw)
            except InvalidOperation:
                raise ValueError("Invalid cost") from None
            if not amount.is_finite() or amount < 0:
                raise ValueError("Invalid cost")
            totals[variant] += amount
    result["data_source"] = "reported_measurements"
    if not unknown:
        result.update(cost_status="known", baseline_cost_usd=str(totals["baseline"]),
                      optimized_cost_usd=str(totals["optimized"]))
        if totals["baseline"] > 0:
            result["savings_percent"] = str(((totals["baseline"] - totals["optimized"]) / totals["baseline"] * 100).quantize(Decimal("0.01")))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurements", type=Path)
    args = parser.parse_args()
    try:
        records = json.loads(args.measurements.read_text(encoding="utf-8")) if args.measurements else None
        print(json.dumps(compare_costs(records), ensure_ascii=False, indent=2))
    except (ValueError, OSError, ArithmeticError):
        parser.error("Invalid or unavailable numeric measurements")
