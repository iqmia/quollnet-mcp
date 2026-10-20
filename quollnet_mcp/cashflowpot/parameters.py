"""Shared descriptions for opaque resource identifiers, never credentials."""
from typing import Annotated

from pydantic import Field, StrictBool

ProjectId = Annotated[str, Field(min_length=1, max_length=128, description="CashflowPot project ID (also called unit_id), returned by project tools; never a user ID or token.")]
CashflowId = Annotated[str, Field(min_length=1, max_length=128, description="Scenario ID returned by CashflowPot tools, belonging to the selected project.")]
ActivityId = Annotated[str, Field(min_length=1, max_length=128, description="Activity ID returned by CashflowPot, belonging to the selected project.")]
FacilityId = Annotated[str, Field(min_length=1, max_length=128, description="Stable financing facility ID within the selected scenario.")]
ActivityIds = Annotated[list[ActivityId], Field(min_length=1, description="IDs of deleted activities to restore in the selected project. Every affected scenario is permission checked.")]
FacilityIds = Annotated[list[FacilityId], Field(description="Every existing facility ID exactly once, in the desired evaluation order; an empty list is valid only if the scenario has no facilities.")]
ConfirmPermanent = Annotated[StrictBool, Field(description="Explicit safeguard for irreversible deletion. Set true only when the user has authorized permanently deleting the identified item and its stated children; false or omission makes no change.")]
