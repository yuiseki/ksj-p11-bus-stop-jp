"""Check the Parquet against the Shapefiles in the zips as served, not against the GeoJSON it came from.

For every prefecture: same number of stops, same name and operator (the .dbf, read as cp932: the .cpg says SJIS, but some names use NEC/IBM extension characters that only cp932 decodes),
the routes and kinds equal the 35 slots of the .dbf joined with commas, the note equals P11_005, every point within 1e-9
degrees of the .shp, the .prj names JGD2011, the GeoParquet crs is an object. Also: the national
file is the 47 prefecture files in code order, ids are unique, n_routes is the length of routes.

The one difference allowed between the .dbf and the GeoJSON of the zip: cp932 decodes the wave
dash byte (0x8160) as U+FF5E (fullwidth tilde) where the source's own GeoJSON has U+301C; the
Parquet follows the GeoJSON; nothing else may differ. The national zip of the source holds the 47
nested prefecture zips; their GeoJSON files must equal those of the prefecture zips.

    uv run python scripts/03_verify.py
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import ksj_bus as k
import pyarrow as pa
import pyarrow.parquet as pq
import shapefile
from shapely import from_wkb

ROOT = Path(__file__).parents[1]
WAVE = str.maketrans({"\uff5e": "\u301c"})


def fix(v):
    return v.translate(WAVE) if isinstance(v, str) else v


def slots(rec, stem: str) -> list[str]:
    out: list[str] = []
    for i in range(1, k.SLOTS + 1):
        v = rec[f"{stem}_{i:02d}"]
        if v:
            out += fix(v).split(",")
    return out


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    par = ROOT / "data" / "parquet"
    allt = pq.read_table(par / "bus_stop.parquet")
    geo = json.loads(allt.schema.metadata[b"geo"])
    assert isinstance(geo["columns"]["geometry"]["crs"], dict), "crs must be PROJJSON"
    assert geo["columns"]["geometry"]["crs"]["id"]["code"] == k.EPSG
    n_total, pieces = 0, []
    for code in k.PREFS:
        t = pq.read_table(par / "prefectures" / f"{code}.parquet")
        pieces.append(t)
        with zipfile.ZipFile(run / k.zip_name(code)) as z:
            base = k.member(z.namelist(), ".shp")[:-4]
            sf = shapefile.Reader(
                shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")),
                dbf=io.BytesIO(z.read(base + ".dbf")),
                encoding="cp932")  # fmt: skip
            prj = z.read(base + ".prj").decode()
        assert "JGD_2011" in prj or "JGD2011" in prj, prj[:80]
        d = t.to_pydict()
        assert len(sf) == t.num_rows, (code, len(sf), t.num_rows)
        worst = 0.0
        for i, sr in enumerate(sf.iterShapeRecords()):
            rec = sr.record.as_dict()
            assert (
                fix(rec["P11_001"]) == d["name"][i] and fix(rec["P11_002"]) == d["operator"][i]
            ), (code, i)
            assert (fix(rec["P11_005"]) or None) == d["note"][i], (code, i)
            assert slots(rec, "P11_003") == d["routes"][i], (code, i)
            assert [str(x) for x in d["kinds"][i]] == slots(rec, "P11_004"), (code, i)
            assert d["n_routes"][i] == len(d["routes"][i]) == len(d["kinds"][i])
            g = from_wkb(d["geometry"][i])
            assert g.geom_type == "Point", (code, i)
            (x, y) = sr.shape.points[0]
            worst = max(worst, abs(x - g.x), abs(y - g.y))
        assert worst < 1e-9, (code, worst)
        assert set(d["pref_code"]) == {code} and set(d["pref"]) == {k.PREFS[code]}
        n_total += t.num_rows
        print(f"{code} {k.PREFS[code]}: {t.num_rows} stops, max coordinate difference {worst:.2e}")
    ids = allt.column("id").to_pylist()
    assert len(set(ids)) == len(ids) == n_total
    assert pa.concat_tables(pieces).equals(allt), (
        "national file is not the prefecture files in order"
    )
    cols = json.loads((par / "columns.json").read_text())
    assert cols["rows"] == n_total
    # The national zip is a bundle of 47 nested zips (P11-22_<code>_GML.zip); each holds the same
    # GeoJSON, byte for byte, as the prefecture's own zip.
    with zipfile.ZipFile(run / k.NATIONAL_ZIP) as nz:
        assert sorted(nz.namelist()) == sorted(f"P11-22_{c}_GML.zip" for c in k.PREFS)
        for code in k.PREFS:
            with zipfile.ZipFile(io.BytesIO(nz.read(f"P11-22_{code}_GML.zip"))) as inner:
                a = inner.read(k.member(inner.namelist(), ".geojson"))
            b = k.read_zip((run / k.zip_name(code)).read_bytes(), ".geojson")
            assert a == b, f"{code}: national zip GeoJSON differs from the prefecture zip"
    print("national zip: the 47 nested GeoJSON files equal the prefecture zips' GeoJSON")
    print(f"OK: {n_total} stops")
    return 0


if __name__ == "__main__":
    sys.exit(main())
