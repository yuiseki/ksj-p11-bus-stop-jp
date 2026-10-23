import io
import json
import zipfile

import ksj_bus as k
import pytest


def props(
    name="X駅", op="京王バス（株）", routes=("A01", "A02"), kinds=("1", "1"), note=None, extra=None
):
    p = {"P11_001": name, "P11_002": op, "P11_005": note}
    for i in range(1, 36):
        p[f"P11_003_{i:02d}"] = None
        p[f"P11_004_{i:02d}"] = None
    if routes:
        p["P11_003_01"] = ",".join(routes)
        p["P11_004_01"] = ",".join(kinds)
    p.update(extra or {})
    return p


def gj(p, geom_type="Point"):
    return json.dumps(
        {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": p,
             "geometry": {"type": geom_type, "coordinates": [139.0, 35.0]}}]}
    ).encode()  # fmt: skip


def test_parse_reads_routes_and_kinds():
    r = k.parse_features(gj(props()))[0]
    assert r["name"] == "X駅" and r["routes"] == ["A01", "A02"] and r["kinds"] == [1, 1]


def test_overflow_slot_continues_the_list():
    p = props(routes=("A", "B"), kinds=("1", "2"), extra={"P11_003_02": "C,D", "P11_004_02": "3,3"})
    r = k.parse_features(gj(p))[0]
    assert r["routes"] == ["A", "B", "C", "D"] and r["kinds"] == [1, 2, 3, 3]


def test_stop_without_routes_is_an_empty_list():
    r = k.parse_features(gj(props(routes=(), kinds=())))[0]
    assert r["routes"] == [] and r["kinds"] == []


def test_note_is_kept():
    assert k.parse_features(gj(props(note="運休中")))[0]["note"] == "運休中"
    assert k.parse_features(gj(props(note="")))[0]["note"] is None
    assert k.parse_features(gj(props(note=None)))[0]["note"] is None


def test_stops_when_routes_and_kinds_differ_in_length():
    with pytest.raises(ValueError, match="2 routes, 1 kinds"):
        k.parse_features(gj(props(kinds=("1",))))


def test_stops_on_unknown_class_code():
    with pytest.raises(ValueError, match="unknown bus class code"):
        k.parse_features(gj(props(kinds=("1", "9"))))


def test_stops_on_new_property():
    with pytest.raises(ValueError, match="unexpected properties"):
        k.parse_features(gj(props(extra={"P11_006": "x"})))


def test_stops_on_other_geometry():
    with pytest.raises(ValueError, match="geometry"):
        k.parse_features(gj(props(), "LineString"))


def test_read_zip_skips_the_metadata():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n in ["a/KS-META-P11.xml", "a/P11-22_13.geojson", "a/P11-22_13.shp"]:
            z.writestr(n, n)
    assert k.read_zip(b.getvalue(), ".geojson") == b"a/P11-22_13.geojson"


def test_geo_metadata_crs_is_an_object():
    assert isinstance(k.geo_metadata({"type": "GeographicCRS"})["columns"]["geometry"]["crs"], dict)


def test_prefs_are_the_47_codes():
    assert list(k.PREFS) == [f"{i:02d}" for i in range(1, 48)]
