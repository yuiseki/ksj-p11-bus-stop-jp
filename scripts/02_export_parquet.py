"""Write one GeoParquet of all stops and one per prefecture from the 47 prefecture zips.

Each row: id (prefecture code and the stop's order in the source file), pref_code, pref,
name (P11_001), operator (P11_002; a municipality for a community bus), routes (the list from
P11_003_01..35), kinds (list of the bus class code of each route, from P11_004_01..35, same order
and length as routes), n_routes, note (P11_005 備考, null when empty), geometry (WKB Point, EPSG:6668 JGD2011 stated in
the GeoParquet metadata as PROJJSON).
data/parquet/bus_stop.parquet holds all stops; data/parquet/prefectures/<code>.parquet one prefecture.

    uv run python scripts/02_export_parquet.py [--version 2026-10-23]
"""

import argparse
import json
import sys
from pathlib import Path

import ksj_bus as k
import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import CRS
from shapely.geometry import shape

ROOT = Path(__file__).parents[1]
SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("pref_code", pa.string()),
        ("pref", pa.string()),
        ("name", pa.string()),
        ("operator", pa.string()),
        ("routes", pa.list_(pa.string())),
        ("kinds", pa.list_(pa.int8())),
        ("n_routes", pa.int32()),
        ("note", pa.string()),
        ("geometry", pa.binary()),
    ]
)


def write(rows: list[dict], path: Path, geo: dict) -> None:
    t = pa.Table.from_pylist(rows, schema=SCHEMA)
    t = t.replace_schema_metadata({b"geo": json.dumps(geo).encode()})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path, compression="zstd")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=None)
    a = ap.parse_args()
    runs = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))
    raw = runs[-1].parent if a.version is None else ROOT / "data" / "raw" / a.version
    manifest = json.loads((raw / "MANIFEST.json").read_text())
    geo = k.geo_metadata(CRS.from_epsg(k.EPSG).to_json_dict())
    rows, counts = [], {}
    for name, meta in manifest["files"].items():
        code = meta["pref_code"]
        if code is None:  # the national zip is only checked, in 03_verify.py
            continue
        feats = k.parse_features(k.read_zip((raw / name).read_bytes(), ".geojson"))
        sub = [
            {"id": f"{code}-{i + 1:05d}", "pref_code": code, "pref": k.PREFS[code],
             "name": f["name"], "operator": f["operator"], "routes": f["routes"],
             "kinds": f["kinds"], "n_routes": len(f["routes"]), "note": f["note"],
             "geometry": shape(f["geometry"]).wkb}
            for i, f in enumerate(feats)
        ]  # fmt: skip
        write(sub, ROOT / "data" / "parquet" / "prefectures" / f"{code}.parquet", geo)
        counts[code] = len(sub)
        rows += sub
    write(rows, ROOT / "data" / "parquet" / "bus_stop.parquet", geo)
    (ROOT / "data" / "parquet" / "columns.json").write_text(
        json.dumps({
            "run": raw.name,
            "rows": len(rows),
            "counts": counts,
            "crs": f"EPSG:{k.EPSG}",
            "columns": {
                "id": "prefecture code and order in the source file",
                "pref_code": "prefecture code of the file the stop came from (01 to 47)",
                "pref": "prefecture name",
                "name": "P11_001 バス停名",
                "operator": "P11_002 バス事業者名 (a municipality for a community bus)",
                "routes": "P11_003_01..35 バス系統, one string per route",
                "kinds": "P11_004_01..35 バス区分コード, one per route, same order as routes",
                "n_routes": "length of routes",
                "note": "P11_005 備考, null when empty (set for some stops of 8 prefectures)",
                "geometry": "WKB Point, EPSG:6668",
            },
            "bus_class_codes": {str(c): v for c, v in k.KINDS.items()},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # fmt: skip
    print(len(rows), counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
