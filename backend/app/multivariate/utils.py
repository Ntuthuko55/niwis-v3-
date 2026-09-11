"""
Shared helpers and the standardised AnalysisResult container.

Every analysis engine returns an :class:`AnalysisResult` which is then turned
into a JSON-serialisable dict for the frontend.  The container holds the
mathematical formulas, result tables, Plotly visualisation specs, an
auto-generated interpretation, limitations and reproducible Python code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def _to_jsonable(obj):
    """Recursively convert numpy/pandas objects into JSON-safe types."""
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if (np.isnan(v) or np.isinf(v)) else v
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return _to_jsonable(obj.tolist())
    if isinstance(obj, pd.Series):
        return _to_jsonable(obj.to_dict())
    if isinstance(obj, pd.DataFrame):
        return _to_jsonable(obj.to_dict(orient="records"))
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    if isinstance(obj, float):
        return None if (np.isnan(obj) or np.isinf(obj)) else obj
    return obj


def plot_to_json(fig) -> dict:
    """Serialise a Plotly figure to a JSON-able dict."""
    return _to_jsonable(fig.to_plotly_json())


def table_to_records(df) -> List[Dict[str, Any]]:
    """Convert a DataFrame to JSON-safe records."""
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if out[col].dtype.kind == "f":
            out[col] = out[col].round(6)
    return _to_jsonable(out.to_dict(orient="records"))


@dataclass
class AnalysisResult:
    """Standard container returned by every analysis engine."""
    method: str
    purpose: str
    category: str
    purpose_latex: str = ""
    data_used: dict = field(default_factory=dict)
    user_config: dict = field(default_factory=dict)
    preprocessing: List[str] = field(default_factory=list)
    preconditions: List[dict] = field(default_factory=list)
    assumptions: List[dict] = field(default_factory=list)
    assumption_summary: str = ""
    applicable: bool = True
    formula: str = ""
    results: dict = field(default_factory=dict)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    visualizations: List[Dict[str, Any]] = field(default_factory=list)
    interpretation: str = ""
    limitations: List[str] = field(default_factory=list)
    python_code: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "method": self.method, "category": self.category,
            "purpose": self.purpose, "purpose_latex": self.purpose_latex,
            "data_used": self.data_used, "user_config": self.user_config,
            "preprocessing": self.preprocessing, "preconditions": self.preconditions,
            "assumptions": self.assumptions, "assumption_summary": self.assumption_summary,
            "applicable": self.applicable, "formula": self.formula,
            "results": _to_jsonable(self.results), "tables": _to_jsonable(self.tables),
            "visualizations": _to_jsonable(self.visualizations),
            "interpretation": self.interpretation, "limitations": self.limitations,
            "python_code": self.python_code, "errors": self.errors,
            "warnings": self.warnings,
        }


