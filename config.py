"""Configuration for the MLIT land-price dashboard.

Regions are parameterized so adding a new city (e.g. Nagoya) later is a one-entry
edit. DATASETS and FIELD_MAP are confirmed/overridden by running ``discover.py``;
until then the data layer falls back to keyword search and heuristic field
extraction so the dashboard still works.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Region:
    key: str
    label: str
    prefecture_code: int          # MLIT prefecture code, e.g. Osaka=27
    city_name: str                # used for address text matching, e.g. "大阪市"
    municipality_codes: list[str] = field(default_factory=list)  # ward codes
    center: tuple[float, float] = (35.0, 135.0)  # map center (lat, lon)
    zoom: int = 11


# --- Target cities -----------------------------------------------------------
# Property data is collected around Osaka & Kobe. Nagoya is a ready-to-activate
# template for the next version (just uncomment).
REGIONS: dict[str, Region] = {
    "osaka": Region(
        key="osaka",
        label="大阪市",
        prefecture_code=27,
        city_name="大阪市",
        municipality_codes=[
            "27102", "27103", "27104", "27106", "27107", "27108", "27109",
            "27111", "27113", "27114", "27115", "27116", "27118", "27119",
            "27120", "27121", "27122", "27123", "27124", "27125", "27126",
            "27127", "27128", "27129",
        ],
        center=(34.6937, 135.5023),
        zoom=11,
    ),
    "kobe": Region(
        key="kobe",
        label="神戸市",
        prefecture_code=28,
        city_name="神戸市",
        municipality_codes=[
            "28101", "28102", "28105", "28106", "28107",
            "28108", "28109", "28110", "28111",
        ],
        center=(34.6901, 135.1955),
        zoom=11,
    ),
    # Next version — uncomment to enable Nagoya:
    # "nagoya": Region(
    #     key="nagoya",
    #     label="名古屋市",
    #     prefecture_code=23,
    #     city_name="名古屋市",
    #     municipality_codes=[f"231{n:02d}" for n in range(1, 17)],
    #     center=(35.1815, 136.9066),
    #     zoom=11,
    # ),
}

DEFAULT_REGION = "osaka"


# --- Themes ------------------------------------------------------------------
@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    search_terms: list[str]       # keywords used to find datasets / records
    dataset_keys: list[str]       # keys into DATASETS (filled by discovery)


THEMES: dict[str, Theme] = {
    "land_price": Theme(
        key="land_price",
        label="地価（公示地価・地価調査）",
        search_terms=["地価公示", "都道府県地価調査", "地価調査"],
        dataset_keys=["land_koji", "land_chosa"],
    ),
    # NOTE: "不動産取引価格" (real-estate transaction price) is NOT served by the
    # MLIT Data Platform API used here. Verified 2026-05-25 via discover.py:
    # 0 hits across all 37 catalogs / ~140 datasets. That data lives on a
    # separate service — 国土交通省 不動産情報ライブラリ
    # (https://www.reinfolib.mlit.go.jp/). Adding transaction support requires
    # a new API client; intentionally omitted to avoid an empty UI tab.
}

DEFAULT_THEME = "land_price"


# --- Discovered identifiers --------------------------------------------------
# Confirmed via discover.py against https://data-platform.mlit.go.jp on
# 2026-05-25. Re-run discover.py if dataset IDs change upstream; the data layer
# falls back to keyword search when DATASETS is empty.
DATASETS: dict[str, str] = {
    "land_koji":  "nlni_ksj-l01",   # 地価公示 (25,565 records nationwide)
    "land_chosa": "nlni_ksj-l02",   # 都道府県地価調査 (21,431 records nationwide)
}

# Logical field → real metadata key. Confirmed from sample records in
# data/sample/sample_地価公示.json. price/year are scalars; use/address are
# JSON objects — the data layer pulls a sub-key via FIELD_SUBKEY.
FIELD_MAP: dict[str, str | None] = {
    "price":   "NLNI:chika_kouji_kakaku",   # int, 円/m²
    "use":     "NLNI:riyo_genkyo",          # dict — see FIELD_SUBKEY
    "address": "NLNI:hyojun_chi_shozai",    # dict — see FIELD_SUBKEY
    "year":    "DPF:year",                  # int (survey year)
}

# When a FIELD_MAP value resolves to a dict, pluck this sub-key out of it.
# None means the field is already a scalar.
FIELD_SUBKEY: dict[str, str | None] = {
    "price":   None,
    "use":     "dai_bunrui",     # 大分類 ("住宅" / "商業" / "工業" / ...)
    "address": "shozai_chiban",  # full address with chiban (most user-friendly)
    "year":    None,
}

# Heuristic candidates (substrings of metadata keys) used when FIELD_MAP is unset.
# Kept as a safety net for future datasets. NOTE: MLIT NLNI fields use romaji
# keys (e.g. `chika_kouji_kakaku`, `hyojun_chi_shozai`), so candidates include
# both kanji and romaji fragments.
FIELD_CANDIDATES: dict[str, list[str]] = {
    "price":   ["価格", "価額", "kouji_kakaku", "kakaku", "u_current_years_price", "price"],
    "use":     ["用途", "利用", "riyo_genkyo", "riyo_kubun", "use", "category", "区分"],
    "address": ["所在", "住所", "地番", "shozai", "hyojun_chi_shozai", "address", "location"],
    "year":    ["DPF:year", "nendo", "year", "年", "価格時点", "調査基準日"],
}

YEAR_ATTRIBUTE = "DPF:year"
PREF_ATTRIBUTE = "DPF:prefecture_code"
MUNI_ATTRIBUTE = "DPF:municipality_code"
DATASET_ATTRIBUTE = "DPF:dataset_id"

# Each 地価公示 record embeds its own multi-decade price history under this
# key, shaped like {"showa58": 0, ..., "heisei30": 167000, "reiwa1": 170000,
# ..., "reiwa8": 197000}. A value of 0 means "not surveyed that year for this
# standard point". The trend builder converts era-year keys (showa/heisei/
# reiwa) to calendar years and aggregates across all points. Using this beats
# querying the API once per year because (a) older year snapshots don't exist
# as separate dataset rows on the platform and (b) one fetch yields ~44 years
# of trend per region. See mlit/data.py:land_price_trend_embedded.
PRICE_HISTORY_FIELD = "NLNI:kouji_kakaku"
