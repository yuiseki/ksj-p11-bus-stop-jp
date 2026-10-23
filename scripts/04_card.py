"""Write data/README.md (the dataset card), data/LICENSE and data/provenance.yaml.

uv run python scripts/04_card.py
"""

import json
import sys
from collections import Counter
from email.utils import parsedate_to_datetime
from pathlib import Path

import ksj_bus as k
import pyarrow.parquet as pq

ROOT = Path(__file__).parents[1]
REPO = "ksj-p11-bus-stop-jp"

CARD = """---
license: cc-by-4.0
license_name: cc-by-4.0
license_link: https://creativecommons.org/licenses/by/4.0/legalcode.ja
language:
- ja
tags:
- japan
- bus
- bus-stop
- public-transport
- geospatial
- ksj
size_categories:
- 100K<n<1M
pretty_name: Bus stops of Japan (国土数値情報 バス停留所 P11, 2022)
---

# {repo}

The bus stops of Japan as the Ministry of Land, Infrastructure, Transport and Tourism's 国土数値情報
バス停留所データ (P11) gives them in its 2022 edition (第3.0版, 令和4年度, made from material of
about August 2022): {rows:,} stops, each with its name, the operator, the routes (系統) that
serve it and the kind of each route. One file for all of Japan and one file per
prefecture (47), as GeoParquet. For the lines of the routes see the sister dataset
`ksj-n07-bus-route-jp`. The four prefectures of Greater Tokyo alone are in
`ksj-p11-bus-stop-greater-tokyo`, which this dataset contains.

## Source

- Data page: <{page}> (国土交通省 国土数値情報ダウンロードサイト, バス停留所).
- Files: the Shapefile zips of the 47 prefectures (`P11-22_01_SHP.zip` to `P11-22_47_SHP.zip`; each
  holds the Shapefile, a GeoJSON and the metadata) and the national zip `P11-22_SHP.zip`, as served.
  Fetched {fetched}; the server states Last-Modified
  {lm}. They are kept unchanged under `raw/{run}/` with their sha256 in `MANIFEST.json`.
- The original materials of the edition, as the page says: stop material collected from local
  governments and bus operators (bus maps, route maps, timetables, stop lists, partly from their
  websites) and GTFS-JP data. The page notes that the dates of the materials vary, and that stops of
  the same operator and the same name on the same road were merged.

## Files

| Path | Content |
|---|---|
| `parquet/bus_stop.parquet` | all {rows:,} stops of the 47 prefecture files, in code order |
| `parquet/prefectures/<code>.parquet` | one prefecture, 2-digit JIS code (01 to 47) |
| `parquet/columns.json` | counts and the bus class codes |
| `raw/{run}/P11-22_<code>_SHP.zip` | the 47 prefecture zips as served |
| `raw/{run}/P11-22_SHP.zip` | the national zip as served (not used for the Parquet, see below) |

## Columns

| Column | Content |
|---|---|
| `id` | prefecture code and the order in the source file, such as `13-00001`; unique over the whole file |
| `pref_code`, `pref` | the prefecture of the file the stop came from |
| `name` | `P11_001`, バス停名 |
| `operator` | `P11_002`, バス事業者名 (a municipality for a community bus) |
| `routes` | list of strings: the 系統 of the stop, from `P11_003_01` to `_35` |
| `kinds` | list of integers, one per route in the same order: the バス区分コード of `P11_004_01` to `_35` (below) |
| `n_routes` | the length of `routes` |
| `note` | `P11_005`, 備考: a remark of the source, null when empty ({note_n:,} stops have one; see below) |
| `geometry` | the stop as WKB Point, EPSG:6668 (JGD2011), stated in the GeoParquet metadata as PROJJSON |

Bus class codes (<{codelist}>): {kind_codes}. Stops by the kinds of their routes in these files:
{kind_counts}.

## What was changed

- The source writes the routes of a stop as one comma-separated string in `P11_003_01` and
  continues in `_02`, `_03`, ... when the 254-character field is full (a cut falls between two
  routes); the same for the kind codes in `P11_004_xx`. Here they are joined and split into lists.
  The list of routes and the list of kinds have the same length in all {rows:,} stops (checked).
- The coordinates, names and route texts are as in the source (the Parquet was checked against the
  `.shp` and `.dbf` of the zips: same count, same text, points equal to 1e-9 degrees). One
  difference of spelling: the GeoJSON of the source writes the wave dash as U+301C, while the
  `.dbf` decoded as cp932 gives U+FF5E for the same byte; the Parquet follows the GeoJSON.
- `P11_005` (備考, remarks) is kept as `note`, null where the source is empty.
- The columns `id`, `pref_code`, `pref` and `n_routes` were added. Nothing was removed, merged
  or corrected.

## Counts

| Prefecture | Stops | Stops with 2 or more routes | Most routes at one stop | Operators |
|---|---|---|---|---|
{count_rows}

## Known issues

- The national zip of the source is a bundle of 47 nested zips (`P11-22_<code>_GML.zip`). The
  GeoJSON in each is byte for byte the GeoJSON of that prefecture's own zip (checked for all 47),
  so the national zip adds nothing; the Parquet is built from the prefecture zips.
- `note` is set for {note_n:,} stops in {note_prefs}. Its values, with their counts: {note_values}.
  The source does not explain them; they are as written.
- Edition of August 2022. Stops and routes that changed since are not reflected.
- The edition leaves out demand-responsive buses (デマンドバス) and highway buses; code 4 of the
  code list does not occur here ({kind_absent}). Code 5 (その他) occurs, and only on the
  {n5:,} stops whose `note` is 「自治体と民間での共同運行」 (checked: every such stop has it, and
  no other stop does).
- The routes of a stop are strings as the operators name them (numbers, names, or the two ends of
  a route, sometimes with a mark such as 【HJ11】). The same route can be written differently at
  different stops, and the file does not link stops into an ordered route.
- In principle the source merged stops of the same operator and the same name on the same road,
  so the two sides of a road are mostly one point, not two.
- {dup_n} stop(s) repeat the name, the operator and the coordinates of another stop in the same
  prefecture; kept, so that the count stays {rows:,}.
- The quality notes of the page say the positions were checked on screen against the GSI
  background maps at zoom levels 15 to 17: the points are placed to that scale, not surveyed.
- The 2010 edition (第2.0版, 平成22年度) of the same layer is marked 非商用 and is not included.

## Licence

The 2022 edition is offered under the site's terms, 国土数値情報ダウンロードサイトコンテンツ利用規約
(<{terms}>), which follow the Japanese government's standard terms of use 2.0 and the Public Data
License 1.0. They allow copying, redistribution and commercial use, are compatible with CC BY 4.0,
and are applied to this edition by its page ("令和4年度: 国土数値情報ダウンロードサイトコンテンツ利用規約
に基づく（オープンデータ）"). This dataset is offered under CC BY 4.0. The terms ask to name the source and
to say that the data were processed, and not to present processed data as if the government
had made it; they leave rights of third parties to the user (the 原典 of this edition includes
materials of operators and municipalities, and the page states no exception). Credit:

> 出典：「国土数値情報（バス停留所データ）」（国土交通省）（{page}）を加工して作成
"""


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    manifest = json.loads((run / "MANIFEST.json").read_text())
    cols = json.loads((ROOT / "data/parquet/columns.json").read_text())
    assert cols["run"] == run.name
    t = pq.read_table(
        ROOT / "data/parquet/bus_stop.parquet",
        columns=["pref_code", "name", "operator", "kinds", "n_routes", "note", "geometry"],
    )
    d = t.to_pydict()
    rows = cols["rows"]
    per = {c: {"n": 0, "multi": 0, "max": 0, "ops": set()} for c in k.PREFS}
    for c, o, n in zip(d["pref_code"], d["operator"], d["n_routes"], strict=True):
        p = per[c]
        p["n"] += 1
        p["multi"] += n >= 2
        p["max"] = max(p["max"], n)
        p["ops"].add(o)
    count_rows = "\n".join(
        f"| {k.PREFS[c]} ({c}) | {p['n']:,} | {p['multi']:,} | {p['max']} | {len(p['ops'])} |"
        for c, p in per.items()
    )
    kc = Counter(tuple(sorted(set(x))) for x in d["kinds"])
    names = {1: "民間", 2: "公営", 3: "コミュニティ", 4: "デマンド", 5: "その他"}
    kind_counts = ", ".join(
        f"{'+'.join(names[i] for i in key) or 'no route'} {n:,}" for key, n in kc.most_common()
    )
    present = {i for key in kc for i in key}
    kind_absent = (
        ", ".join(f"{i} {k.KINDS[i]}" for i in k.KINDS if i not in present) or "none absent"
    )
    dup_n = sum(
        n - 1
        for n in Counter(
            zip(d["pref_code"], d["name"], d["operator"], d["geometry"], strict=True)
        ).values()
        if n > 1
    )
    assert min(d["n_routes"]) >= 1, "a stop without a route: say so in the card"
    notes = Counter(n for n in d["note"] if n)
    note_pref = sorted({c for c, n in zip(d["pref_code"], d["note"], strict=True) if n})
    note_n = sum(notes.values())
    note_prefs = f"{len(note_pref)} prefectures (" + ", ".join(k.PREFS[c] for c in note_pref) + ")"
    note_values = ", ".join(f"「{v}」 {n:,}" for v, n in notes.most_common())
    lms = sorted({e["last_modified"] for e in manifest["files"].values()})
    stamps = sorted(parsedate_to_datetime(x) for x in lms)
    lms_text = (
        lms[0] if len(lms) == 1
        else f"{stamps[0]:%Y-%m-%d %H:%M:%S} to {stamps[-1]:%Y-%m-%d %H:%M:%S} UTC (it differs per file)"
    )  # fmt: skip
    n5 = sum(5 in x for x in d["kinds"])
    assert (
        n5
        == sum(
            5 in x and n == "自治体と民間での共同運行"
            for x, n in zip(d["kinds"], d["note"], strict=True)
        )
        == notes["自治体と民間での共同運行"]
    ), "code 5 and the joint-operation note no longer coincide"
    card = CARD.format(
        repo=REPO, rows=rows, page=k.PAGE_URL, terms=k.TERMS_URL, codelist=k.CODELIST_URL,
        run=run.name, fetched=run.name, lm=lms_text, count_rows=count_rows,
        kind_codes=", ".join(f"{c} {v}" for c, v in k.KINDS.items()), kind_counts=kind_counts,
        kind_absent=kind_absent, dup_n=dup_n, note_n=note_n, note_prefs=note_prefs,
        note_values=note_values, n5=n5,
        pref_files=", ".join(f"`{c}` {k.PREFS[c]}" for c in k.PREFS),
        files_list=", ".join(f"`{n}`" for n in manifest["files"]),
    )  # fmt: skip
    data = ROOT / "data"
    (data / "README.md").write_text(card, encoding="utf-8")
    (data / "LICENSE").write_text(
        "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/legalcode)\n\n"
        "The bus stops are from 国土数値情報 バス停留所データ (P11, 2022 edition) of the Ministry of\n"
        "Land, Infrastructure, Transport and Tourism, published under the site's terms\n"
        f"({k.TERMS_URL}; government standard terms of use 2.0, compatible with CC BY 4.0),\n"
        "processed as described in README.md.\n"
        f"Credit: 出典：「国土数値情報（バス停留所データ）」（国土交通省）（{k.PAGE_URL}）を加工して作成\n",
        encoding="utf-8",
    )
    (data / "provenance.yaml").write_text(
        f"source: 国土数値情報 バス停留所データ (P11), 2022 edition (令和4年度), 国土交通省\nurl: {k.PAGE_URL}\n"
        f"terms: {k.TERMS_URL}\nrun: {run.name}\nretrieved: {run.name}\nlast_modified: {lms}\n"
        f"files: {len(manifest['files'])}\nrows: {rows}\n",
        encoding="utf-8",
    )
    print("wrote data/README.md, LICENSE, provenance.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
