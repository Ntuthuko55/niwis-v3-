"""
Dataset intelligence engine.

Loads a CSV/XLSX file, profiles it, detects variable types, and produces a
comprehensive data-quality report that every downstream analysis consumes.
"""
from __future__ import annotations

import io
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd

from .type_detector import TypeDetector


_DATASET_REGISTRY: Dict[str, Dict[str, Any]] = {}


class DatasetEngine:
    """Profile a DataFrame and describe its data quality."""

    def __init__(self, max_categories: int = 15):
        self.type_detector = TypeDetector(max_categories=max_categories)

    @staticmethod
    def _read_file(path_or_stream, filename: str) -> pd.DataFrame:
        lower = filename.lower()
        if lower.endswith((".xlsx", ".xls")):
            return pd.read_excel(path_or_stream, engine="openpyxl")
        if isinstance(path_or_stream, (bytes, bytearray)):
            return pd.read_csv(io.BytesIO(path_or_stream), sep=None, engine="python")
        return pd.read_csv(path_or_stream, sep=None, engine="python")

    @staticmethod
    def register(df, filename):
        ds_id = str(uuid.uuid4())
        _DATASET_REGISTRY[ds_id] = {"df": df, "filename": filename, "n_rows": len(df)}
        return ds_id

    @staticmethod
    def get(df_id):
        entry = _DATASET_REGISTRY.get(df_id)
        return entry["df"] if entry else None

    @staticmethod
    def info(df_id):
        entry = _DATASET_REGISTRY.get(df_id)
        if entry is None:
            return None
        return {"id": df_id, "filename": entry["filename"],
                "n_rows": entry["n_rows"], "columns": list(entry["df"].columns)}

    def profile(self, df, type_map=None):
        """Return a full data-quality profile for df."""
        n_rows, n_cols = df.shape
        type_df = self.type_detector.detect(df)
        if type_map:
            type_df = type_df.copy()
            type_df["detected_type"] = type_df.apply(
                lambda r: type_map.get(r["column"], r["detected_type"]), axis=1)
        buckets = self.type_detector.categorize(type_df)
        missing = df.isna().sum()
        missing_total = int(missing.sum())
        missing_per_col = {str(c): {"missing": int(missing[c]),
            "pct": float(missing[c] / max(n_rows, 1))} for c in df.columns}
        duplicate_rows = int(df.duplicated().sum())
        constant_cols = [str(c) for c in df.columns if df[c].nunique(dropna=True) <= 1]
        outlier_info = self._detect_outliers(df, buckets["numeric"])
        suspicious = self._detect_suspicious(df)
        return {
            "dimensions": {"rows": int(n_rows), "columns": int(n_cols)},
            "variable_counts": {"numeric": len(buckets["numeric"]),
                "categorical": len(buckets["categorical"]), "binary": len(buckets["binary"]),
                "ordinal": len(buckets["ordinal"]), "id": len(buckets["id"]),
                "date": len(buckets["date"]), "other": len(buckets["other"])},
            "missing": {"total_missing": missing_total, "per_column": missing_per_col},
            "duplicate_rows": duplicate_rows, "constant_columns": constant_cols,
            "outliers": outlier_info, "suspicious_values": suspicious,
            "variables": type_df.to_dict(orient="records"), "buckets": buckets}

    def _detect_outliers(self, df, numeric_cols):
        info = {}
        for col in numeric_cols:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) < 4:
                continue
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            n_out = int(((series < lower) | (series > upper)).sum())
            if n_out > 0:
                info[col] = {"count": n_out, "pct": float(n_out / max(len(series), 1) * 100),
                    "lower_bound": float(lower), "upper_bound": float(upper)}
        return info

    def _detect_suspicious(self, df):
        suspicious = []
        sentinels = {0, -1, -9, -99, -999, 99, 999, 9999, -8, -7}
        for col in df.columns:
            series = df[col]
            if series.dtype == "object":
                continue
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.dropna().empty:
                continue
            vals = set(numeric.round(3).dropna().astype(float).unique())
            hits = vals & {float(s) for s in sentinels}
            if hits:
                n_hit = int((numeric.isin(hits)).sum())
                if 0 < n_hit < len(numeric) * 0.5:
                    suspicious.append({"column": str(col),
                        "sentinels": sorted(float(h) for h in hits),
                        "count": n_hit, "note": "Placeholder / sentinel values detected"})
        return suspicious

    def get_numeric(self, df, type_map=None):
        profile = self.profile(df, type_map=type_map)
        numeric_cols = [v["column"] for v in profile["variables"]
                        if v["detected_type"] in ("numeric", "ordinal", "binary")]
        if not numeric_cols:
            return pd.DataFrame(index=df.index)
        return df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    def get_column_types(self, df):
        td = self.type_detector.detect(df)
        return {str(r["column"]): r["detected_type"] for _, r in td.iterrows()}


