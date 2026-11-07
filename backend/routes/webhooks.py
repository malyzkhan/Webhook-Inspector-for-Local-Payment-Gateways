import asyncio
import base64
import json
import logging
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from typing import Any
from urllib.parse import parse_qs, quote_from_bytes

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from pymongo.errors import PyMongoError

from database import get_webhooks_collection
from models import WebhookEvent

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_PAYLOAD_BYTES = 64 * 1024
STREAM_QUEUE_SIZE = 100
active_streams: dict[str, set[asyncio.Queue[str]]] = {}


def _decode(raw_body: bytes) -> str:
    return raw_body.decode("utf-8", errors="replace")


def _parse_multipart(raw_body: bytes, content_type: str) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1", errors="replace")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + raw_body
    )
    fields: dict[str, Any] = {}
    if not message.is_multipart():
        return {"raw": _decode(raw_body)}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        if filename is not None:
            value: Any = {
                "filename": filename,
                "content_type": part.get_content_type(),
                "size": len(part.get_payload(decode=True) or b""),
            }
        else:
            value = part.get_content()
            if isinstance(value, bytes):
                value = _decode(value)
        if name in fields:
            previous = fields[name]
            fields[name] = previous + [value] if isinstance(previous, list) else [previous, value]
        else:
            fields[name] = value
    return fields


def _parse_body(raw_body: bytes, content_type: str) -> Any:
    if not raw_body:
        return {}
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "application/json" or media_type.endswith("+json"):
        try:
            return json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"raw": _decode(raw_body), "parse_error": "Invalid JSON"}
    if media_type == "application/x-www-form-urlencoded":
        return {
            key: values[0] if len(values) == 1 else values
            for key, values in parse_qs(_decode(raw_body), keep_blank_values=True).items()
        }
    if media_type == "multipart/form-data":
        return _parse_multipart(raw_body, content_type)
    return _decode(raw_body)


def _gateway_for(body: Any, query_params: dict[str, Any]) -> str:
    keys: set[str] = set(query_params)
    if isinstance(body, dict):
        keys.update(body)
    if any(key.startswith("pp_") for key in keys):
        return "JazzCash"
    if {"orderId", "paymentToken"}.intersection(keys):
        return "EasyPaisa"
    return "Generic"


def _publish(endpoint_id: str, serialized_event: str) -> None:
    for queue in tuple(active_streams.get(endpoint_id, set())):
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(serialized_event)
        except asyncio.QueueFull:
            pass


@router.api_route("/wh/{endpoint_id}", methods=["GET", "POST"])
async def receive_webhook(endpoint_id: str, request: Request):
    raw_query_bytes = request.scope.get("query_string", b"")
    if len(raw_query_bytes) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Request payload exceeds 64 KiB")

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) + len(raw_query_bytes) > MAX_PAYLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Request payload exceeds 64 KiB")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")

    raw_body_buffer = bytearray()
    async for chunk in request.stream():
        raw_body_buffer.extend(chunk)
        if len(raw_body_buffer) + len(raw_query_bytes) > MAX_PAYLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Request payload exceeds 64 KiB")
    raw_body = bytes(raw_body_buffer)

    content_type = request.headers.get("content-type", "")
    parsed_body = _parse_body(raw_body, content_type)
    grouped_query_params: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        grouped_query_params.setdefault(key, []).append(value)
    query_params = {
        key: values[0] if len(values) == 1 else values
        for key, values in grouped_query_params.items()
    }
    event = WebhookEvent(
        id=str(uuid.uuid4()),
        endpoint_id=endpoint_id,
        method=request.method,
        headers=dict(request.headers),
        query_params=query_params,
        parsed_body=parsed_body,
        raw_query=quote_from_bytes(raw_query_bytes, safe="=&;%+,:/?@!$'()*-._~"),
        raw_body_base64=base64.b64encode(raw_body).decode("ascii"),
        content_type=content_type,
        client_ip=request.client.host if request.client else None,
        gateway=_gateway_for(parsed_body, query_params),
        created_at=datetime.now(timezone.utc),
        response_status=200,
    )
    document = event.model_dump()
    try:
        await get_webhooks_collection().insert_one(document)
    except PyMongoError as exc:
        logger.exception("Could not store webhook event for endpoint %s", endpoint_id)
        raise HTTPException(status_code=503, detail="Webhook storage unavailable") from exc

    payload = event.model_dump(mode="json")
    _publish(endpoint_id, json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    return {"status": "received", "id": event.id, "code": "000"}


@router.get("/stream/{endpoint_id}")
async def stream_webhooks(endpoint_id: str):
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=STREAM_QUEUE_SIZE)
    active_streams.setdefault(endpoint_id, set()).add(queue)

    async def event_stream():
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            listeners = active_streams.get(endpoint_id)
            if listeners is not None:
                listeners.discard(queue)
                if not listeners:
                    active_streams.pop(endpoint_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/endpoints/{endpoint_id}/history", response_model=list[WebhookEvent])
async def webhook_history(endpoint_id: str):
    try:
        cursor = (
            get_webhooks_collection()
            .find({"endpoint_id": endpoint_id}, {"_id": 0})
            .sort("created_at", -1)
            .limit(50)
        )
        documents = await cursor.to_list(length=50)
    except PyMongoError as exc:
        logger.exception("Could not read webhook history for endpoint %s", endpoint_id)
        raise HTTPException(status_code=503, detail="Webhook storage unavailable") from exc

    try:
        return [WebhookEvent.model_validate(document) for document in documents]
    except ValidationError as exc:
        logger.exception("Stored webhook history is invalid for endpoint %s", endpoint_id)
        raise HTTPException(status_code=500, detail="Stored webhook data is invalid") from exc
