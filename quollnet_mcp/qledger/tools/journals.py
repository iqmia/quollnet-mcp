from uuid import UUID
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger.models import ClassificationQuery, JournalQuery
from quollnet_mcp.qledger.models_accounting import (
    JournalCreate,
    JournalPatch,
    PostRequest,
    ReversalRequest,
)
from .common import call, unit_path, object_id


def _entry(unit_id, entry_id):
    return unit_path(unit_id) + "/journal-entries/" + object_id(entry_id)


async def list_qledger_transactions(
    unit_id: UUID, query: JournalQuery = JournalQuery()
):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/journal-entries",
        unit_id=unit_id,
        query=query,
    )


async def list_qledger_classification_values(unit_id: UUID, query: ClassificationQuery):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/journal-classifications",
        unit_id=unit_id,
        query=query,
    )


async def get_qledger_transaction(unit_id: UUID, entry_id: UUID):
    return await call(qledger_client, "GET", _entry(unit_id, entry_id), unit_id=unit_id)


async def create_qledger_transaction(
    unit_id: UUID, request: JournalCreate, idempotency_key: str
):
    return await call(
        qledger_client,
        "POST",
        unit_path(unit_id) + "/journal-entries",
        unit_id=unit_id,
        body=request,
        key=idempotency_key,
    )


async def update_qledger_transaction(
    unit_id: UUID, entry_id: UUID, request: JournalPatch
):
    return await call(
        qledger_client,
        "PATCH",
        _entry(unit_id, entry_id),
        unit_id=unit_id,
        body=request,
    )


async def post_qledger_transaction(unit_id: UUID, entry_id: UUID, request: PostRequest):
    return await call(
        qledger_client,
        "POST",
        _entry(unit_id, entry_id) + "/post",
        unit_id=unit_id,
        body=request,
    )


async def reverse_qledger_transaction(
    unit_id: UUID, entry_id: UUID, request: ReversalRequest, idempotency_key: str
):
    return await call(
        qledger_client,
        "POST",
        _entry(unit_id, entry_id) + "/reverse",
        unit_id=unit_id,
        body=request,
        key=idempotency_key,
    )


async def delete_qledger_transaction(unit_id: UUID, entry_id: UUID):
    return await call(
        qledger_client, "DELETE", _entry(unit_id, entry_id), unit_id=unit_id
    )
