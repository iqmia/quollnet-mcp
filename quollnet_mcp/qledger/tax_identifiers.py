"""Deterministic advisory checks, never tax-authority or ownership verification."""

import re
from typing import Literal

from .models import Schema

PT_ALGORITHM_SOURCE = (
    "https://proderam2020.madeira.gov.pt/images/documentos/Candidaturas/ACAPORAMA/"
    "Guia_de_validacao_M19.2.1.ii_a8b41.pdf"
)


class TaxIdentifierCheck(Schema):
    country_code: str
    identifier: str
    normalized_identifier: str
    supported: bool
    status: Literal[
        "passed", "failed_checksum", "invalid_format", "unsupported_country"
    ]
    format_valid: bool | None = None
    checksum_valid: bool | None = None
    algorithm: str | None = None
    weighted_sum: int | None = None
    expected_check_digit: str | None = None
    supplied_check_digit: str | None = None
    verification_status: Literal["unverified"] = "unverified"
    blocking: Literal[False] = False
    warnings: list[str]


def check_tax_identifier(
    identifier: str, country_code: str = "PT"
) -> TaxIdentifierCheck:
    """Check PT NIF/NIPC modulo 11; unsupported country rules are never guessed."""
    country = country_code.strip().upper()
    warning = (
        "Advisory format/checksum check only; no tax-authority lookup, assignment, "
        "ownership, active status or VAT-registration verification."
    )
    result = {
        "country_code": country,
        "identifier": identifier,
        "normalized_identifier": identifier,
        "supported": country == "PT",
        "warnings": [warning],
    }
    if country != "PT":
        return TaxIdentifierCheck(
            **result,
            status="unsupported_country",
            algorithm=None,
        )
    value = identifier.strip(" ")
    if value[:2].upper() == "PT":
        value = value[2:].strip(" ")
    value = value.replace(" ", "").replace("-", "")
    result.update(normalized_identifier=value, algorithm="PT_NIF_MOD11_9_TO_2_V1")
    if re.fullmatch(r"[1-9][0-9]{8}", value) is None:
        result["warnings"].append(
            "PT input must contain nine ASCII digits with a nonzero first digit. "
            "Only a PT prefix, spaces and hyphens are normalized. No number was corrected."
        )
        return TaxIdentifierCheck(**result, status="invalid_format", format_valid=False)
    weighted_sum = sum(
        int(digit) * weight
        for digit, weight in zip(value[:8], range(9, 1, -1), strict=True)
    )
    remainder = weighted_sum % 11
    expected = str(0 if remainder in (0, 1) else 11 - remainder)
    passed = value[-1] == expected
    if not passed:
        result["warnings"].append(
            "Checksum failed. Preserve the supplied identifier; an expected check digit "
            "is diagnostic, not a proposed corrected tax identifier. Authorized storage "
            "may retain this warning and user confirmation as metadata."
        )
    return TaxIdentifierCheck(
        **result,
        status="passed" if passed else "failed_checksum",
        format_valid=True,
        checksum_valid=passed,
        weighted_sum=weighted_sum,
        expected_check_digit=expected,
        supplied_check_digit=value[-1],
    )
