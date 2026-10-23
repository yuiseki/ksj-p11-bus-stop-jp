"""Shared helpers: the files of 国土数値情報 バス停留所 (P11, 2022 edition) and how to read them."""

import io
import json
import zipfile

PREFS = {
    "01": "北海道",
    "02": "青森県",
    "03": "岩手県",
    "04": "宮城県",
    "05": "秋田県",
    "06": "山形県",
    "07": "福島県",
    "08": "茨城県",
    "09": "栃木県",
    "10": "群馬県",
    "11": "埼玉県",
    "12": "千葉県",
    "13": "東京都",
    "14": "神奈川県",
    "15": "新潟県",
    "16": "富山県",
    "17": "石川県",
    "18": "福井県",
    "19": "山梨県",
    "20": "長野県",
    "21": "岐阜県",
    "22": "静岡県",
    "23": "愛知県",
    "24": "三重県",
    "25": "滋賀県",
    "26": "京都府",
    "27": "大阪府",
    "28": "兵庫県",
    "29": "奈良県",
    "30": "和歌山県",
    "31": "鳥取県",
    "32": "島根県",
    "33": "岡山県",
    "34": "広島県",
    "35": "山口県",
    "36": "徳島県",
    "37": "香川県",
    "38": "愛媛県",
    "39": "高知県",
    "40": "福岡県",
    "41": "佐賀県",
    "42": "長崎県",
    "43": "熊本県",
    "44": "大分県",
    "45": "宮崎県",
    "46": "鹿児島県",
    "47": "沖縄県",
}
BASE = "https://nlftp.mlit.go.jp/ksj/gml/data/P11/P11-22/"
PAGE_URL = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-v3_0.html"
TERMS_URL = "https://nlftp.mlit.go.jp/ksj/other/agreement.html"
CODELIST_URL = "https://nlftp.mlit.go.jp/ksj/gml/codelist/BusClassCd.html"
EPSG = 6668  # JGD2011, as the .prj and the GeoJSON of the source state
NATIONAL_ZIP = "P11-22_SHP.zip"
SLOTS = 35  # P11_003_01..35 (routes) and P11_004_01..35 (bus class codes)
KINDS = {
    1: "路線バス（民間）",
    2: "路線バス（公営）",
    3: "コミュニティバス",
    4: "デマンドバス",
    5: "その他",
}


def zip_name(code: str) -> str:
    return f"P11-22_{code}_SHP.zip"


def member(names: list[str], suffix: str) -> str:
    found = [n for n in names if n.endswith(suffix) and "KS-META" not in n]
    if len(found) != 1:
        raise ValueError(f"expected one *{suffix} in the zip, found {found}")
    return found[0]


def read_zip(data: bytes, suffix: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(member(z.namelist(), suffix))


def join_slots(props: dict, stem: str) -> list[str]:
    """The comma-joined values of stem_01..stem_35 as one list.

    The source packs all routes of a stop into stem_01 separated by commas and continues in the
    next slot when the 254-character field of the Shapefile is full (a cut between two items).
    """
    out: list[str] = []
    for i in range(1, SLOTS + 1):
        v = props[f"{stem}_{i:02d}"]
        if v not in (None, ""):
            out += v.split(",")
    return out


def parse_features(geojson: bytes) -> list[dict]:
    """One dict per stop: name, operator, routes (list), kinds (list of int, one per route), point.

    note is P11_005 (備考; None when empty). A route list and a kind list of different length mean
    the source changed, so that stops the run.
    """
    d = json.loads(geojson)
    expected = {"P11_001", "P11_002", "P11_005"}
    expected |= {f"P11_003_{i:02d}" for i in range(1, SLOTS + 1)}
    expected |= {f"P11_004_{i:02d}" for i in range(1, SLOTS + 1)}
    out = []
    for f in d["features"]:
        p = f["properties"]
        if set(p) != expected:
            raise ValueError(f"unexpected properties {sorted(set(p) ^ expected)}")
        if f["geometry"]["type"] != "Point":
            raise ValueError(f"unexpected geometry {f['geometry']['type']}")
        routes, kinds = join_slots(p, "P11_003"), join_slots(p, "P11_004")
        if len(routes) != len(kinds):
            raise ValueError(f"{p['P11_001']}: {len(routes)} routes, {len(kinds)} kinds")
        bad = [x for x in kinds if not x.isdigit() or int(x) not in KINDS]
        if bad:
            raise ValueError(f"{p['P11_001']}: unknown bus class code {bad}")
        out.append(
            {
                "name": p["P11_001"],
                "operator": p["P11_002"],
                "routes": routes,
                "kinds": [int(x) for x in kinds],
                "note": p["P11_005"] or None,
                "geometry": f["geometry"],
            }
        )
    return out


def geo_metadata(crs: dict) -> dict:
    return {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["Point"], "crs": crs}},
    }
