from uuid import UUID
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger.models import VersionRequest, RecordLinkCreate
from quollnet_mcp.qledger.models_records import (
    RecordCreate,
    RecordPatch,
    RecordPost,
    RecordQuery,
    ProductSearchQuery,
)
from .common import call, unit_path, object_id


def _record(unit_id, record_id):
    return unit_path(unit_id) + "/records/" + object_id(record_id)


async def list_qledger_records(unit_id: UUID, query: RecordQuery = RecordQuery()):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/records",
        unit_id=unit_id,
        query=query,
    )


async def get_qledger_record(unit_id: UUID, record_id: UUID):
    return await call(
        qledger_client, "GET", _record(unit_id, record_id), unit_id=unit_id
    )


async def create_qledger_record(
    unit_id: UUID, request: RecordCreate, idempotency_key: str
):
    return await call(
        qledger_client,
        "POST",
        unit_path(unit_id) + "/records",
        unit_id=unit_id,
        body=request,
        key=idempotency_key,
    )


async def update_qledger_record(unit_id: UUID, record_id: UUID, request: RecordPatch):
    return await call(
        qledger_client,
        "PATCH",
        _record(unit_id, record_id),
        unit_id=unit_id,
        body=request,
    )


async def delete_qledger_record(
    unit_id: UUID, record_id: UUID, request: VersionRequest
):
    return await call(
        qledger_client,
        "DELETE",
        _record(unit_id, record_id),
        unit_id=unit_id,
        body=request,
    )


async def copy_qledger_record(
    unit_id: UUID, record_id: UUID, request: VersionRequest, idempotency_key: str
):
    return await call(
        qledger_client,
        "POST",
        _record(unit_id, record_id) + "/copy",
        unit_id=unit_id,
        body=request,
        key=idempotency_key,
    )


async def post_qledger_record(unit_id: UUID, record_id: UUID, request: RecordPost):
    return await call(
        qledger_client,
        "POST",
        _record(unit_id, record_id) + "/post",
        unit_id=unit_id,
        body=request,
    )


async def unpost_qledger_record(
    unit_id: UUID, record_id: UUID, request: VersionRequest
):
    return await call(
        qledger_client,
        "POST",
        _record(unit_id, record_id) + "/unpost",
        unit_id=unit_id,
        body=request,
    )


async def list_qledger_record_links(unit_id: UUID, record_id: UUID):
    return await call(
        qledger_client, "GET", _record(unit_id, record_id) + "/links", unit_id=unit_id
    )


async def link_qledger_record(
    unit_id: UUID, record_id: UUID, request: RecordLinkCreate, idempotency_key: str
):
    return await call(
        qledger_client,
        "POST",
        _record(unit_id, record_id) + "/links",
        unit_id=unit_id,
        body=request,
        key=idempotency_key,
    )


async def unlink_qledger_record(unit_id: UUID, record_id: UUID, link_id: UUID):
    return await call(
        qledger_client,
        "DELETE",
        _record(unit_id, record_id) + "/links/" + object_id(link_id),
        unit_id=unit_id,
    )


async def replace_qledger_record_link(
    unit_id: UUID, record_id: UUID, link_id: UUID, request: RecordLinkCreate
):
    return await call(
        qledger_client,
        "PATCH",
        _record(unit_id, record_id) + "/links/" + object_id(link_id),
        unit_id=unit_id,
        body=request,
    )


async def search_qledger_products(unit_id: UUID, query: ProductSearchQuery):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/products/search",
        unit_id=unit_id,
        query=query,
    )
