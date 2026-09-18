"""Base class and shared helpers for all analysis engines."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..core.assumptions import AssumptionResult, PreconditionCheck, summarize_assumptions
from ..utils import AnalysisResult, plot_to_json, table_to_records, _to_jsonable
from ..core.dataset_engine import DatasetEngine


class BaseAnalysis:
    """Common base for all 11 analysis engines."""

    name = "Unnamed Analysis"
    category = "Uncategorized"
    tags: List[str] = []

    def __init__(self, dataset_engine: DatasetEngine):
        self.engine = dataset_engine

    def run(self, df_id: str, config: Dict[str, Any],
            type_map: Optional[Dict[str, str]] = None) -> dict:
        df = self.engine.get(df_id)
        if df is None:
            raise ValueError(f"Dataset id '{df_id}' not found")
        missing_columns = self._missing_config_columns(df, config)
        if missing_columns:
            result = self._empty_result()
            result.applicable = False
            result.user_config = config
            result.errors.append(
                "The selected column(s) are not in this dataset: "
                + ", ".join(missing_columns)
                + ". Refresh your variable selection and try again."
            )
            return result.to_dict()
        result = self._safe_run(df, config, type_map)
        return result.to_dict()

    @staticmethod
    def _missing_config_columns(df: pd.DataFrame, config: Dict[str, Any]) -> List[str]:
        """Return requested analysis columns that are absent from the dataset.

        This guard applies before a method indexes the DataFrame.  It keeps
        stale UI selections and direct API requests from becoming a pandas
        ``KeyError`` or an internal-server error.
        """
        list_fields = (
            "variables", "independent_variables", "dependent_variables",
            "set_a", "set_b", "predictors", "x_variables", "y_variables",
        )
        scalar_fields = (
            "dependent_variable", "grouping_variable", "class_variable",
            "row_variable", "column_variable",
        )
        selected: List[Any] = []
        for field in list_fields:
            value = config.get(field, [])
            if isinstance(value, (list, tuple)):
                selected.extend(value)
        for field in scalar_fields:
            value = config.get(field)
            if value:
                selected.append(value)
        available = set(df.columns)
        return sorted({str(column) for column in selected if column not in available})

    def _safe_run(self, df, config, type_map):
        try:
            return self.run_analysis(df, config, type_map)
        except Exception as exc:
            import traceback
            result = self._empty_result()
            result.errors.append(self._human_read_error(exc, traceback.format_exc()))
            result.applicable = False
            return result

    def run_analysis(self, df, config, type_map=None):
        raise NotImplementedError

    def _empty_result(self) -> AnalysisResult:
        return AnalysisResult(
            method=self.name, category=self.category,
            purpose=getattr(self, "_purpose_text", "Statistical analysis."),
            purpose_latex=getattr(self, "_purpose_latex", ""),
        )

    def _human_read_error(self, exc: Exception, tb: str) -> str:
        msg = str(exc)
        low = msg.lower()
        if "singular" in low:
            return ("Computation failed because the data matrix is singular "
                    "(perfect multicollinearity or insufficient variation). "
                    "Try removing or combining correlated variables, or adding "
                    "more observations.")
        if "not enough" in low and "observations" in low:
            return "There are not enough observations to perform this analysis reliably."
        if "could not convert" in low or "unable to parse" in low:
            return ("One or more selected columns contain non-numeric values that "
                    "could not be interpreted. Check the variable types or clean the data.")
        if "no numeric" in low or "no columns" in low:
            return "The selected configuration contains no valid numeric variables."
        if "convergence" in low:
            return ("The iterative algorithm did not converge. Try standardising "
                    "the variables, reducing the number of components, or increasing "
                    "the number of iterations.")
        first_line = tb.strip().splitlines()[-1] if tb else msg
        cls_name = getattr(self, "name", "analysis")
        return f"The {cls_name} could not be completed: {first_line}"

    def _variable_info(self, df, cols, type_map=None) -> List[dict]:
        types = self.engine.get_column_types(df)
        if type_map:
            types.update(type_map)
        info = []
        for c in cols:
            t = types.get(c, "unknown")
            series = df[c]
            info.append({"name": str(c), "type": t,
                         "n_unique": int(series.nunique(dropna=True)),
                         "n_missing": int(series.isna().sum()),
                         "sample": series.dropna().astype(str).unique()[:5].tolist()})
        return _to_jsonable(info)

    def _numeric_matrix(self, df, cols, drop_missing="drop") -> pd.DataFrame:
        sub = df[cols].copy()
        sub = sub.apply(pd.to_numeric, errors="coerce").astype(float)
        if drop_missing == "drop":
            return sub.dropna()
        if drop_missing == "impute_mean":
            return sub.fillna(sub.mean())
        return sub

    def _add_code(self, result: AnalysisResult, code: str) -> None:
        import textwrap
        result.python_code = textwrap.dedent(code).lstrip("\n")

    @staticmethod
    def _fig(spec: dict) -> dict:
        return {"spec": spec}


