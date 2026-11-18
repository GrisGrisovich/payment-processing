from hmac import compare_digest
from typing import Annotated, cast

from fastapi import Depends, Header, HTTPException, Request

from app.application.services.payments import PaymentService

APIKey = Annotated[str | None, Header(alias="X-API-Key")]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=255)]


def require_api_key(request: Request, api_key: APIKey = None) -> None:
    if api_key is None or not compare_digest(
        api_key.encode(), request.app.state.api_key
    ):
        raise HTTPException(status_code=401, detail="Invalid API key")


def get_payment_service(request: Request) -> PaymentService:
    return cast(PaymentService, request.app.state.payment_service)


PaymentServiceDependency = Annotated[PaymentService, Depends(get_payment_service)]
