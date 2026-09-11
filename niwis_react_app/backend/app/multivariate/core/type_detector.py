"""
Variable type detection.

Classifies each column of a dataset into one of:
    numeric, categorical, binary, ordinal, id, date

The classifier is data-driven and does not require the user to pre-specify
types.  Results can be overridden by the user before running an analysis.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

import numpy as np
import pandas as pd


# Columns whose *name* strongly suggests an identifier role.
_ID_NAME_PATTERNS = [
    re.compile(r"^id$|_id$|id_|uuid|uid|\bfid\b|_code$|_code\b|\bkey$|_key$|key_", re.I),
]

_MONTH_NAMES = set(
    "jan feb mar apr may jun jul aug sep oct nov dec "
    "january february march april may june july august september october november december"
    .split()
)



def _looks_like_id(series: pd.Series, nunique: int, nrows: int) -> bool:
    """Near-unique identifier (very high cardinality, mostly unique).

    Only applied to *non-numeric* columns.  Numeric columns that happen to be
    unique (e.g. an ID-numbered index) are still caught via the name pattern,
    but a continuous numeric variable with many distinct values must NOT be
    labelled an identifier.
    """
    if nunique == 0 or nrows == 0:
        return False
    name = str(series.name).lower()
    name_match = name and any(p.search(name) for p in _ID_NAME_PATTERNS)
    # Name-based match works for any dtype.
    if name_match:
        return True
    # Ratio-based match only for object/string columns and with a minimum
    # absolute cardinality, otherwise small datasets mis-classify continuous
    # variables as identifiers.
    if series.dtype == "object":
        if nunique / max(nrows, 1) >= 0.90 and nunique >= 30:
            return True
    return False


def _detect_datetime(series: pd.Series, non_null: pd.Series) -> bool:
    """Try to interpret an object series as datetime."""
    sample = non_null.astype(str).str.strip()
    if sample.empty:
        return False
    # Avoid sending ordinary category labels (for example, ``Graduate`` or
    # ``Female``) through the permissive date parser.  Besides being costly,
    # that parser emits warnings for ambiguous non-date strings.
    looks_date_like = sample.str.contains(
        r"\d|[-/]") | sample.str.lower().isin(_MONTH_NAMES)
    if looks_date_like.mean() < 0.75:
        return False
    try:
        parsed = pd.to_datetime(sample, errors="raise")
        parsed_non_null = parsed.notna()
        if parsed_non_null.sum() == 0:
            return False
        # Accept if a large fraction parses cleanly.
        return bool(parsed_non_null.mean() >= 0.75)
    except (ValueError, TypeError, OverflowError):
        return False


def detect_variable_type(series: pd.Series, max_categories: int = 15) -> str:
    """Return the detected type for a single pandas Series."""
    nrows = len(series)
    if nrows == 0:
        return "categorical"

    non_null = series.dropna()
    if non_null.empty:
        return "categorical"

    n_unique = int(non_null.nunique(dropna=True))

    # date?  (only meaningful for object columns)
    if series.dtype == "object":
        if _detect_datetime(series, non_null):
            return "date"

    # numeric coercion
    numeric_series = pd.to_numeric(non_null, errors="coerce")
    numeric_mask = ~numeric_series.isna()
    n_numeric = int(numeric_mask.sum())
    numeric_ratio = n_numeric / max(len(non_null), 1)
    is_numeric = numeric_ratio >= 0.8 and n_numeric >= 3

    # ------------------------------------------------------------------ ID?
    if _looks_like_id(series, n_unique, nrows):
        return "id"

    # ------------------------------------------------------------------ binary
    if n_unique <= 2:
        vals = set(non_null.astype(str).str.strip().str.lower().unique())
        binary_synonyms = {"0", "1", "true", "false", "yes", "no", "y", "n", "t", "f"}
        if vals.issubset(binary_synonyms) or (is_numeric and n_unique == 2):
            return "binary"
        return "categorical"

        # ------------------------------------------------------------------ numeric / ordinal
    if is_numeric:
        if numeric_ratio == 1.0:
            as_int = numeric_series.dropna()
            is_int_like = np.allclose(as_int, np.round(as_int), rtol=0, atol=1e-9)
            val_range = float(as_int.max() - as_int.min()) if len(as_int) else 0.0
            # A genuinely ordinal / rating-scale variable: integer values,
            # few distinct levels and a narrow numeric range that does not
            # span many categories.  Wide-range integers (Age, Income) stay
            # numeric.
            if (is_int_like and n_unique <= max_categories
                    and val_range <= max_categories and n_unique < nrows):
                return "ordinal"
        return "numeric"

    # ------------------------------------------------------------------ object / non-numeric
    if n_unique <= max_categories:
        lowered = non_null.astype(str).str.strip().str.lower()
        ordinal_tokens = {
            "low", "medium", "high", "below", "above", "mild", "moderate",
            "severe", "good", "bad", "excellent", "fair", "poor",
            "small", "large", "none", "minimal", "mod",
        }
        if lowered.isin(ordinal_tokens).any() and n_unique <= 5:
            return "ordinal"
        return "categorical"

    return "categorical"



class TypeDetector:
    """Detects the statistical type of every column in a DataFrame."""

    def __init__(self, max_categories: int = 15):
        self.max_categories = max_categories

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a DataFrame describing the detected type of each column.

        Columns of the returned frame:
            column, dtype, detected_type, n_unique, n_missing,
            missing_pct, sample_values
        """
        rows: List[Dict[str, Any]] = []
        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)
            n_unique = int(series.nunique(dropna=True))
            n_missing = int(series.isna().sum())
            detected = detect_variable_type(series, self.max_categories)
            sample_vals = series.dropna().astype(str).unique()[:5].tolist()
            rows.append(
                {
                    "column": str(col),
                    "dtype": dtype,
                    "detected_type": detected,
                    "n_unique": n_unique,
                    "n_missing": n_missing,
                    "missing_pct": float(round(n_missing / max(len(series), 1) * 100, 2)),
                    "sample_values": sample_vals,
                }
            )
        return pd.DataFrame(rows)

    def categorize(self, type_df: pd.DataFrame) -> Dict[str, List[str]]:
        """Group columns by detected type into convenience buckets."""
        buckets: Dict[str, List[str]] = {
            "numeric": [], "categorical": [], "binary": [], "ordinal": [],
            "id": [], "date": [], "other": [],
        }
        for _, row in type_df.iterrows():
            t = row["detected_type"]
            col = str(row["column"])
            if t in buckets:
                buckets[t].append(col)
            else:
                buckets["other"].append(col)
        buckets["categorical_like"] = (
            buckets["categorical"] + buckets["ordinal"] + buckets["binary"]
        )
        return buckets


