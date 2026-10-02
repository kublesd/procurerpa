"""Best-effort wakeups only: messages never authorize or execute procurement."""

import asyncio
import hashlib
import json
from contextlib import suppress

from redis.asyncio import Redis

from skyvern.config import settings


def channel_name(org_id: str, approval_id: str) -> str:
    scope = json.dumps([org_id, approval_id]).encode()
    return "approval:notice:" + hashlib.sha256(scope).hexdigest()


def redis_client() -> Redis:
    return Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=2)


async def publish_update(org_id: str, approval_id: str, status: str, actor_id: str) -> None:
    client = None
    try:
        client = redis_client()
        async with asyncio.timeout(2):
            await client.publish(channel_name(org_id, approval_id), json.dumps({
                "approval_id": approval_id, "status": status, "actor_id": actor_id,
            }))
    except Exception:
        # A missed wakeup is recovered by database polling; never log Redis credentials.
        pass
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()


async def wait_for_update(org_id: str, approval_id: str, timeout: int) -> None:
    client = pubsub = None
    try:
        client = redis_client()
        pubsub = client.pubsub()
        async with asyncio.timeout(timeout):
            await pubsub.subscribe(channel_name(org_id, approval_id))
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                if message is not None and message["type"] == "message":
                    return  # Do not deserialize or trust the message body.
    except Exception:
        pass  # Timeout, lost event, or Redis outage: caller rereads PostgreSQL.
    finally:
        for resource in (pubsub, client):
            if resource is not None:
                with suppress(Exception):
                    await resource.aclose()
