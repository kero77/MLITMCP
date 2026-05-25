"""High-level, cached data access for the dashboard.

Turns MLIT GraphQL responses into tidy pandas DataFrames. Region is always a
parameter (Osaka now, Nagoya later) and field extraction falls back to heuristics
until discover.py fills in config.FIELD_MAP.
"""

from __future__ import annotations

import json
import re

import pandas as pd
import streamlit as st

import config
from mlit import queries as q
from mlit.client import MlitClient

# Safety cap on how many point records to pull per (region, year).
_MAX_POINTS = 6000
_PAGE = 500


@st.cache_resource
def get_client() -> MlitClient:
    return MlitClient()


# --- metadata helpers --------------------------------------------------------
def _as_dict(metadata) -> dict:
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _resolve_key(md: dict, logical: str) -> str | None:
    """Find the metadata key for a logical field via FIELD_MAP or candidates."""
    configured = config.FIELD_MAP.get(logical)
    if configured and configured in md:
        return configured
    for cand in config.FIELD_CANDIDATES.get(logical, []):
        for key in md:
            if cand in key:
                return key
    return None


def _pluck(md: dict, logical: str):
    """Resolve a logical field to its scalar value.

    Several MLIT NLNI fields hold dicts (e.g. ``NLNI:riyo_genkyo`` →
    ``{"dai_bunrui": "住宅", ...}``). When the resolved value is a dict, we
    pull out ``FIELD_SUBKEY[logical]`` if set, otherwise the first scalar value.
    Returns ``None`` when the field isn't present.
    """
    key = _resolve_key(md, logical)
    if key is None:
        return None
    value = md.get(key)
    if isinstance(value, dict):
        subkey = getattr(config, "FIELD_SUBKEY", {}).get(logical)
        if subkey and subkey in value:
            return value.get(subkey)
        # Fallback: first non-dict, non-list scalar in the dict.
        for v in value.values():
            if v is not None and not isinstance(v, (dict, list)):
                return v
        return None
    return value


def _to_float(value) -> float | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d.]", "", str(value))
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def _theme_term(theme_key: str) -> str:
    return config.THEMES[theme_key].search_terms[0]


def _theme_dataset_ids(theme_key: str) -> list[str]:
    keys = config.THEMES[theme_key].dataset_keys
    return [config.DATASETS[k] for k in keys if config.DATASETS.get(k)]


def _attr_filter(region_key: str, year: int | None, theme_key: str) -> str:
    region = config.REGIONS[region_key]
    filters: list[tuple[str, str | int]] = [
        (config.PREF_ATTRIBUTE, region.prefecture_code)
    ]
    if year is not None:
        filters.append((config.YEAR_ATTRIBUTE, year))
    ds_ids = _theme_dataset_ids(theme_key)
    if len(ds_ids) == 1:
        filters.append((config.DATASET_ATTRIBUTE, ds_ids[0]))
    return q.attr_and(filters)


# --- raw fetch ---------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_points(region_key: str, theme_key: str, year: int) -> list[dict]:
    """Paginated `search` for one region+year, returns raw result dicts.

    Uses term-based fallback when dataset_id is unknown.
    """
    client = get_client()
    attr = _attr_filter(region_key, year, theme_key)
    term = "" if _theme_dataset_ids(theme_key) else _theme_term(theme_key)
    out: list[dict] = []
    first = 0
    while first < _MAX_POINTS:
        data = client.execute(
            q.search_q(term=term, size=_PAGE, first=first, attribute_filter=attr)
        )
        block = (data.get("search") or {})
        results = block.get("searchResults") or []
        out.extend(results)
        total = block.get("totalNumber") or 0
        first += _PAGE
        if first >= total or not results:
            break
    return out


def _records_to_df(records: list[dict], region_key: str) -> pd.DataFrame:
    region = config.REGIONS[region_key]
    rows = []
    for r in records:
        md = _as_dict(r.get("metadata"))
        rows.append(
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "year": r.get("year"),
                "lat": r.get("lat"),
                "lon": r.get("lon"),
                "price": _to_float(_pluck(md, "price")),
                "use": _pluck(md, "use"),
                "address": _pluck(md, "address") or r.get("title"),
                "dataset_id": r.get("dataset_id"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Narrow to the target city by address text. If nothing matches (address
    # format may differ), keep the prefecture-level rows rather than dropping all.
    mask = df["address"].fillna("").str.contains(region.city_name, na=False)
    if mask.any():
        df = df[mask]
    return df.reset_index(drop=True)


# --- public API --------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def available_years(region_key: str, theme_key: str) -> list[int]:
    """Survey years present for a region/theme (newest first)."""
    client = get_client()
    region = config.REGIONS[region_key]
    attr = q.attr_and([(config.PREF_ATTRIBUTE, region.prefecture_code)])
    term = "" if _theme_dataset_ids(theme_key) else _theme_term(theme_key)
    data = client.execute(q.count_by_year_q(attribute_filter=attr, term=term))
    slices = (data.get("countData") or {}).get("slices") or []
    years: list[int] = []
    for s in slices:
        try:
            years.append(int(str(s.get("attributeValue"))))
        except (ValueError, TypeError):
            continue
    return sorted(set(years), reverse=True)


def land_price_points(region_key: str, year: int, use: str | None = None) -> pd.DataFrame:
    """Detailed point-level records for one city and year."""
    df = _records_to_df(_fetch_points(region_key, "land_price", year), region_key)
    if use and not df.empty and "use" in df:
        df = df[df["use"] == use].reset_index(drop=True)
    return df


def land_price_history(
    region_key: str, years: list[int], use: str | None = None
) -> pd.DataFrame:
    """Stacked point records across multiple years (basis for trends)."""
    frames = [land_price_points(region_key, y, use) for y in years]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def land_price_trend(region_key: str, years: list[int], use: str | None = None) -> pd.DataFrame:
    """Yearly mean / median price per m², point count, and year-over-year %."""
    hist = land_price_history(region_key, years, use)
    if hist.empty or hist["price"].dropna().empty:
        return pd.DataFrame()
    grp = (
        hist.dropna(subset=["price"])
        .groupby("year")["price"]
        .agg(mean_price="mean", median_price="median", count="count")
        .reset_index()
        .sort_values("year")
    )
    grp["yoy_pct"] = grp["mean_price"].pct_change() * 100
    return grp.reset_index(drop=True)


def transaction_prices(region_key: str, year: int) -> pd.DataFrame:
    """Real-estate transaction-price records for one city and year."""
    return _records_to_df(_fetch_points(region_key, "transaction", year), region_key)


def land_use_options(region_key: str, year: int) -> list[str]:
    df = land_price_points(region_key, year)
    if df.empty or "use" not in df:
        return []
    return sorted(x for x in df["use"].dropna().unique())
