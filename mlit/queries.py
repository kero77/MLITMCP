"""GraphQL query string builders for the MLIT Data Platform API.

Query shapes verified against the official mlit-dpf-mcp client implementation.
Numeric codes are emitted unquoted; string values are JSON-escaped and quoted.
"""

from __future__ import annotations

import json
from typing import Iterable

# Result field presets for `search` / `getAllData`.
FIELDS_BASIC = "id title lat lon year dataset_id catalog_id"
FIELDS_DETAIL = "id title lat lon year theme metadata dataset_id catalog_id hasThumbnail"


def _scalar(value: str | int | float) -> str:
    """Render a GraphQL scalar: ints unquoted, everything else quoted+escaped."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


def attr_and(filters: Iterable[tuple[str, str | int]]) -> str:
    """Build an `attributeFilter: { AND: [...] }` clause from (name, value) pairs.

    Returns an empty string when there are no filters.
    """
    clauses = [
        f'{{ attributeName: "{name}", is: {_scalar(value)} }}' for name, value in filters
    ]
    if not clauses:
        return ""
    return f"attributeFilter: {{ AND: [ {', '.join(clauses)} ] }}"


def search_q(
    term: str = "",
    size: int = 50,
    first: int = 0,
    attribute_filter: str = "",
    fields: str = FIELDS_DETAIL,
    phrase_match: bool = True,
) -> str:
    parts = [f"first: {first}", f"size: {size}", f"term: {_scalar(term)}",
             f"phraseMatch: {'true' if phrase_match else 'false'}"]
    if attribute_filter:
        parts.append(attribute_filter)
    args = ", ".join(parts)
    return f"query {{ search({args}) {{ totalNumber searchResults {{ {fields} }} }} }}"


def get_all_data_q(
    attribute_filter: str = "",
    size: int = 500,
    term: str = "",
    token: str | None = None,
) -> str:
    if token:
        return (
            f"query {{ getAllData(nextDataRequestToken: {_scalar(token)}) "
            f"{{ nextDataRequestToken data {{ id title metadata }} }} }}"
        )
    parts = [f"size: {size}", f"term: {_scalar(term)}", "phraseMatch: false"]
    if attribute_filter:
        parts.append(attribute_filter)
    args = ", ".join(parts)
    return (
        f"query {{ getAllData({args}) "
        f"{{ nextDataRequestToken data {{ id title metadata }} }} }}"
    )


def count_by_year_q(
    attribute_filter: str = "",
    term: str = "",
    year_attribute: str = "DPF:year",
    size: int = 100,
) -> str:
    """Count records sliced by survey year — basis for the trend timeline."""
    parts = [f"term: {_scalar(term)}", "phraseMatch: false"]
    if attribute_filter:
        parts.append(attribute_filter)
    parts.append(
        "sliceSetting: { type: \"attribute\", attributeSliceSetting: "
        f"{{ attributeName: {_scalar(year_attribute)}, size: {size} }} }}"
    )
    args = ", ".join(parts)
    return (
        f"query {{ countData({args}) {{ dataCount "
        f"slices {{ attributeName attributeValue dataCount }} }} }}"
    )


def data_catalog_q(ids: list[str] | None = None) -> str:
    arg = "IDs: " + (json.dumps(ids, ensure_ascii=False) if ids else "null")
    return (
        f"query {{ dataCatalog({arg}) "
        f"{{ id title datasets {{ id title data_count }} }} }}"
    )


def suggest_q(term: str, attribute_filter: str = "") -> str:
    parts = [f"term: {_scalar(term)}", "phraseMatch: true"]
    if attribute_filter:
        parts.append(attribute_filter)
    args = ", ".join(parts)
    return f"query {{ suggest({args}) {{ totalNumber suggestions {{ name cnt }} }} }}"


def prefecture_q() -> str:
    return "query { prefecture { code name } }"


def municipalities_q(pref_codes: list[str]) -> str:
    arg = json.dumps(pref_codes, ensure_ascii=False)
    return (
        f"query {{ municipalities(prefCodes: {arg}) "
        f"{{ code_as_string prefecture_code name }} }}"
    )
