"""Download the bus stops (P11, 2022 edition) of Japan from 国土数値情報.

Each prefecture's Shapefile zip and the national one (it holds the Shapefile, a GeoJSON and the metadata) is fetched
once, sequentially, one second apart (403 or 429 stops the run), hashed and recorded in
data/raw/<version>/MANIFEST.json with the Last-Modified the server states. The data page, the
bus-class code list and the site terms are saved under data/docs/. The version is the UTC date
of the first run.

    uv run python scripts/01_download.py [--version 2026-10-23]
"""

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import ksj_bus as k

ROOT = Path(__file__).parents[1]
UA = "ksj-p11-bus-stop-jp/0.1 (+https://github.com/yuiseki/ksj-p11-bus-stop-jp)"


def get(url: str) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read(), {h.lower(): v for h, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise SystemExit(f"{e.code} from {url}: stopping") from e
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    raw = ROOT / "data" / "raw" / a.version
    docs = ROOT / "data" / "docs"
    raw.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    for url, name in ((k.PAGE_URL, "KsjTmplt-P11-v3_0.html"), (k.TERMS_URL, "agreement.html"),
                      (k.CODELIST_URL, "BusClassCd.html")):  # fmt: skip
        time.sleep(1)
        (docs / name).write_bytes(get(url)[0])
    files = {}
    for code in k.PREFS:
        time.sleep(1)
        url = k.BASE + k.zip_name(code)
        body, h = get(url)
        (raw / k.zip_name(code)).write_bytes(body)
        with zipfile.ZipFile(raw / k.zip_name(code)) as z:
            members = z.namelist()
        files[k.zip_name(code)] = {
            "url": url,
            "pref_code": code,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "last_modified": h.get("last-modified"),
            "members": members,
        }
        print(code, k.PREFS[code], len(body))
    time.sleep(1)
    url = k.BASE + k.NATIONAL_ZIP
    body, h = get(url)
    (raw / k.NATIONAL_ZIP).write_bytes(body)
    with zipfile.ZipFile(raw / k.NATIONAL_ZIP) as z:
        members = z.namelist()
    files[k.NATIONAL_ZIP] = {
        "url": url,
        "pref_code": None,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "last_modified": h.get("last-modified"),
        "members": members,
    }
    print("national", len(body))
    (raw / "MANIFEST.json").write_text(
        json.dumps({"retrieved": a.version, "page": k.PAGE_URL, "files": files},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
