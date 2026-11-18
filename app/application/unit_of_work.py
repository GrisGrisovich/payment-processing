from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from app.application.repositories import OutboxRepository, PaymentRepository


class UnitOfWork(Protocol):
    @property
    def payments(self) -> PaymentRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...


type UnitOfWorkFactory = Callable[[], AbstractAsyncContextManager[UnitOfWork]]
