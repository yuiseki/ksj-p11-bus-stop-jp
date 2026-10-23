# ksj-p11-bus-stop-jp

Reproducible collection of the bus stops (国土数値情報 P11, 2022 edition) of all 47
prefectures. The dataset card is generated into `data/README.md` (not tracked; the data is
published at https://huggingface.co/datasets/yuiseki/ksj-p11-bus-stop-jp).

```
uv run python scripts/01_download.py      # 47 prefecture zips + the national zip + the data page, terms, code list (data/raw/<date>, data/docs)
uv run python scripts/02_export_parquet.py
uv run python scripts/03_verify.py        # Parquet vs the .shp/.dbf of the zips
uv run python scripts/04_card.py
uv run python src/publish.py [--push]     # dry run by default
```

Code: MIT. Data: CC BY 4.0, see the card.
