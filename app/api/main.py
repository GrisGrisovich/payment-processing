from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.routes import router
from app.application.services.payments import PaymentService
from app.infrastructure.database import make_engine, postgres_unit_of_work
from app.settings import ApiSettings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = ApiSettings()
    engine = make_engine(settings.database_url)
    sessions = async_sessionmaker(engine)
    app.state.api_key = settings.api_key.get_secret_value().encode()
    app.state.payment_service = PaymentService(partial(postgres_unit_of_work, sessions))
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="Payment processing",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(router)
