from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class WebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    endpoint_id: str
    method: str
    headers: dict[str, str]
    query_params: dict[str, Any]
    parsed_body: Any
    raw_query: str
    raw_body_base64: str
    content_type: str
    client_ip: str | None
    gateway: str
    created_at: datetime
    response_status: int
