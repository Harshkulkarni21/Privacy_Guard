from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def write_parquet(df: pd.DataFrame, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    previous_bytes = path.read_bytes() if path.exists() else None
    tmp_path = path.with_name(f".{path.name}.tmp")

    try:
        df.to_parquet(tmp_path, index=False)
        tmp_path.replace(path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        if previous_bytes is not None:
            path.write_bytes(previous_bytes)
        raise
    else:
        if tmp_path.exists():
            tmp_path.unlink()


def read_parquet(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)
