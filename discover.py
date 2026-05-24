"""One-off discovery script for the MLIT Data Platform.

Run this once with a valid MLIT_API_KEY to find:
  1. dataset_ids for land-price (地価公示 / 地価調査) and transaction-price datasets
  2. the metadata field names that hold price / use / address / year
  3. which survey years are available

Outputs suggested values to paste into config.py (DATASETS, FIELD_MAP) and saves
sample records to data/sample/ for offline UI development.

    python discover.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import config
from mlit.client import MlitClient
from mlit import queries as q

SAMPLE_DIR = Path(__file__).resolve().parent / "data" / "sample"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

KEYWORDS = ["地価公示", "都道府県地価調査", "地価調査", "不動産取引価格", "取引価格"]


def _print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def list_catalogs(client: MlitClient) -> list[dict]:
    _print_header("1. Catalogs / datasets (matching land-price & transaction keywords)")
    data = client.execute(q.data_catalog_q())
    catalogs = data.get("dataCatalog") or []
    matched: list[dict] = []
    for cat in catalogs:
        for ds in cat.get("datasets") or []:
            title = ds.get("title") or ""
            if any(kw in title for kw in KEYWORDS):
                row = {
                    "catalog_id": cat.get("id"),
                    "catalog_title": cat.get("title"),
                    "dataset_id": ds.get("id"),
                    "dataset_title": title,
                    "data_count": ds.get("data_count"),
                }
                matched.append(row)
                print(f"  - {title}  [dataset_id={ds.get('id')}, count={ds.get('data_count')}]")
    if not matched:
        print("  (no catalog titles matched keywords — will rely on keyword search)")
    (SAMPLE_DIR / "catalogs.json").write_text(
        json.dumps(matched, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return matched


def sample_records(client: MlitClient, term: str, pref_code: int = 27) -> list[dict]:
    """Fetch a small sample for a keyword in Osaka and dump raw metadata."""
    _print_header(f"2. Sample records for term='{term}' (prefecture={pref_code})")
    attr = q.attr_and([(config.PREF_ATTRIBUTE, pref_code)])
    data = client.execute(q.search_q(term=term, size=5, attribute_filter=attr))
    results = (data.get("search") or {}).get("searchResults") or []
    print(f"  totalNumber={ (data.get('search') or {}).get('totalNumber') }, showing {len(results)}")
    for r in results[:3]:
        print(f"\n  --- record {r.get('id')} | dataset_id={r.get('dataset_id')} | year={r.get('year')} ---")
        md = r.get("metadata")
        if isinstance(md, str):
            try:
                md = json.loads(md)
            except (ValueError, TypeError):
                pass
        print(f"  title: {r.get('title')}")
        if isinstance(md, dict):
            for k, v in md.items():
                print(f"    {k}: {str(v)[:80]}")
        else:
            print(f"  metadata: {str(md)[:300]}")
    safe = term.replace("/", "_")
    (SAMPLE_DIR / f"sample_{safe}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results


def years_available(client: MlitClient, term: str, pref_code: int = 27) -> None:
    _print_header(f"3. Available years for term='{term}' (prefecture={pref_code})")
    attr = q.attr_and([(config.PREF_ATTRIBUTE, pref_code)])
    data = client.execute(q.count_by_year_q(attribute_filter=attr, term=term))
    cd = data.get("countData") or {}
    print(f"  total dataCount={cd.get('dataCount')}")
    slices = sorted(
        cd.get("slices") or [], key=lambda s: str(s.get("attributeValue"))
    )
    for s in slices:
        print(f"    year {s.get('attributeValue')}: {s.get('dataCount')} records")


def suggest_field_map(samples: list[dict]) -> None:
    _print_header("4. Suggested FIELD_MAP (inspect & paste into config.py)")
    key_counter: Counter[str] = Counter()
    for r in samples:
        md = r.get("metadata")
        if isinstance(md, str):
            try:
                md = json.loads(md)
            except (ValueError, TypeError):
                continue
        if isinstance(md, dict):
            key_counter.update(md.keys())
    if not key_counter:
        print("  (no dict metadata seen — check sample output above)")
        return
    print("  metadata keys seen:")
    for k, c in key_counter.most_common():
        print(f"    {k}  (x{c})")
    guess = {}
    for logical, cands in config.FIELD_CANDIDATES.items():
        for key in key_counter:
            if any(c in key for c in cands):
                guess[logical] = key
                break
    print("\n  best-guess FIELD_MAP:")
    print("  " + json.dumps(guess, ensure_ascii=False))


def main() -> None:
    client = MlitClient()
    print(f"Using base_url={client.base_url}")
    list_catalogs(client)
    all_samples: list[dict] = []
    for term in ["地価公示", "不動産取引価格"]:
        all_samples += sample_records(client, term)
        years_available(client, term)
    suggest_field_map(all_samples)
    print(f"\nSamples written to {SAMPLE_DIR}")


if __name__ == "__main__":
    main()
