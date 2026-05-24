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
    "transaction": Theme(
        key="transaction",
        label="不動産取引価格",
        search_terms=["不動産取引価格", "取引価格情報"],
        dataset_keys=["transaction"],
    ),
}

DEFAULT_THEME = "land_price"


# --- Discovered identifiers --------------------------------------------------
# Filled in by running discover.py. Leave empty to fall back to keyword search.
DATASETS: dict[str, str] = {
    # "land_koji": "<dataset_id>",
    # "land_chosa": "<dataset_id>",
    # "transaction": "<dataset_id>",
}

# Maps logical fields to the metadata key found in real records. When a value is
# None the data layer uses the candidate lists below (heuristic extraction).
FIELD_MAP: dict[str, str | None] = {
    "price": None,     # price per square meter (円/m²)
    "use": None,       # land-use category (用途区分)
    "address": None,   # location / address (所在)
    "year": None,      # survey year
}

# Heuristic candidates (substrings of metadata keys) used when FIELD_MAP is unset.
FIELD_CANDIDATES: dict[str, list[str]] = {
    "price": ["価格", "価額", "u_current_years_price", "price", "円", "地価"],
    "use": ["用途", "利用", "use", "category", "区分"],
    "address": ["所在", "住所", "地番", "address", "location", "名称"],
    "year": ["DPF:year", "year", "年", "価格時点", "調査基準日"],
}

YEAR_ATTRIBUTE = "DPF:year"
PREF_ATTRIBUTE = "DPF:prefecture_code"
MUNI_ATTRIBUTE = "DPF:municipality_code"
DATASET_ATTRIBUTE = "DPF:dataset_id"
