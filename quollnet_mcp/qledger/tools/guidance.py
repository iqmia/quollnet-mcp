"""Read-only guidance scoped to the selected authenticated QEntries unit."""

from typing import Annotated
from uuid import UUID

from pydantic import Field, StrictStr

from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger import auth
from quollnet_mcp.qledger.line_guidance import LineItemGuidance, line_item_guidance
from quollnet_mcp.qledger.tax_identifiers import (
    TaxIdentifierCheck,
    TaxIdentifierRequest,
)

from .common import call, unit_path


async def check_qledger_tax_identifier(
    unit_id: UUID,
    identifier: Annotated[StrictStr, Field(max_length=128)],
    country_code: Annotated[StrictStr, Field(pattern=r"^[A-Za-z]{2}$")],
    identifier_type: Annotated[
        StrictStr, Field(min_length=1, max_length=32)
    ] = "tax_id",
) -> TaxIdentifierCheck:
    result = await call(
        qledger_client,
        "POST",
        unit_path(unit_id) + "/tax-identifiers/check",
        unit_id=unit_id,
        body=TaxIdentifierRequest(
            country_code=country_code,
            identifier=identifier,
            identifier_type=identifier_type,
        ),
    )
    return TaxIdentifierCheck.model_validate(result)


async def get_qledger_line_item_guidance(unit_id: UUID) -> LineItemGuidance:
    await auth.unit_token(unit_id)
    return line_item_guidance()
