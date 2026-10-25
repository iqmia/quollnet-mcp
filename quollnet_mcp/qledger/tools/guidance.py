"""Read-only guidance scoped to the selected authenticated QEntries unit."""

from typing import Annotated
from uuid import UUID

from pydantic import Field, StrictStr

from quollnet_mcp.qledger import auth
from quollnet_mcp.qledger.line_guidance import LineItemGuidance, line_item_guidance
from quollnet_mcp.qledger.tax_identifiers import (
    TaxIdentifierCheck,
    check_tax_identifier,
)


async def check_qledger_tax_identifier(
    unit_id: UUID,
    identifier: Annotated[StrictStr, Field(min_length=1, max_length=128)],
    country_code: Annotated[StrictStr, Field(pattern=r"^[A-Za-z]{2}$")] = "PT",
) -> TaxIdentifierCheck:
    await auth.unit_token(unit_id)
    return check_tax_identifier(identifier, country_code)


async def get_qledger_line_item_guidance(unit_id: UUID) -> LineItemGuidance:
    await auth.unit_token(unit_id)
    return line_item_guidance()
