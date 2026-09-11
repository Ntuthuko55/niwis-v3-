"""
Assumption-checking framework.

Every analysis produces a list of ``AssumptionResult`` objects describing
whether each prerequisite for the method is satisfied.  This keeps the
"statistical assistant" behaviour consistent across all 11 methods.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd


@dataclass
class AssumptionResult:
    """A single prerequisite check for a statistical method."""

    name: str
    status: str  # "pass" | "warning" | "fail"
    detail: str = ""
    metrics: dict = field(default_factory=dict)

    @property
    def overall_pass(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "metrics": self.metrics,
        }


@dataclass
class PreconditionCheck:
    """Higher-level applicability decision (before detailed assumptions)."""

    name: str
    status: str  # "pass" | "warning" | "fail"
    detail: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def summarize_assumptions(assumptions: List[AssumptionResult]) -> str:
    """Produce a short text verdict for a list of assumptions."""
    passes = sum(1 for a in assumptions if a.status == "pass")
    warnings = sum(1 for a in assumptions if a.status == "warning")
    fails = sum(1 for a in assumptions if a.status == "fail")
    verdict = "PASS" if fails == 0 and warnings == 0 else (
        "WARNING" if fails == 0 else "FAIL"
    )
    return f"{verdict} ({passes} pass, {warnings} warning, {fails} fail)"


def normality_test(values: np.ndarray) -> dict:
    """Run Shapiro-Wilk (preferred) or D'Agostino normality test."""
    from scipy import stats

    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 3:
        return {"test": "none", "statistic": None, "p": None,
                "normal": None, "note": "Too few observations"}
    if len(values) <= 5000:
        try:
            stat, p = stats.shapiro(values)
            test_name = "Shapiro-Wilk"
        except Exception:
            stat, p = stats.normaltest(values)
            test_name = "D'Agostino K^2"
    else:
        stat, p = stats.normaltest(values)
        test_name = "D'Agostino K^2"
    return {"test": test_name, "statistic": float(stat), "p": float(p),
            "normal": bool(p > 0.05), "note": ""}


def homoscedasticity_test(residuals: np.ndarray, groups: np.ndarray) -> dict:
    """Levene's test for equal variances across groups."""
    from scipy import stats

    residuals = np.asarray(residuals, dtype=float)
    groups = np.asarray(groups)
    unique_groups = np.unique(groups[~pd.isna(groups)])
    if len(unique_groups) < 2:
        return {"test": "Levene", "statistic": None, "p": None,
                "equal_var": None, "note": "Single group"}
    samples = [residuals[groups == g] for g in unique_groups]
    samples = [s for s in samples if len(s) > 0]
    if len(samples) < 2:
        return {"test": "Levene", "statistic": None, "p": None,
                "equal_var": None, "note": "Insufficient groups"}
    try:
        stat, p = stats.levene(*samples)
        return {"test": "Levene", "statistic": float(stat), "p": float(p),
                "equal_var": bool(p > 0.05), "note": ""}
    except Exception as exc:  # pragma: no cover - defensive
        return {"test": "Levene", "statistic": None, "p": None,
                "equal_var": None, "note": str(exc)}


def multicollinearity_vif(X: pd.DataFrame) -> pd.DataFrame:
    """Compute Variance Inflation Factors for a (numeric) design matrix."""
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    X = X.dropna(axis=1, how="all").astype(float)
    if "const" not in X.columns:
        Xc = pd.concat([pd.Series(1.0, index=X.index, name="const"), X], axis=1)
    else:
        Xc = X
    vifs = []
    for i, col in enumerate(Xc.columns):
        if col == "const":
            continue
        try:
            val = float(variance_inflation_factor(Xc.values, i))
        except Exception:
            val = float("nan")
        vifs.append({"variable": col, "VIF": val})
    return pd.DataFrame(vifs)


def correlation_matrix(X: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation matrix for numeric columns."""
    numeric = X.select_dtypes(include=[np.number])
    return numeric.corr(method="pearson")


def bartlett_sphericity(X: pd.DataFrame) -> dict:
    """Bartlett's test of sphericity (used for PCA / Factor Analysis)."""
    X = X.select_dtypes(include=[np.number]).dropna()
    corr = X.corr().values
    if corr.ndim != 2 or corr.shape[0] < 2:
        return {"statistic": None, "p": None, "note": "Insufficient variables"}
    try:
        from factor_analyzer.factor_analyzer import calculate_bartlett_sphericity

        chi2, p = calculate_bartlett_sphericity(X)
        return {"statistic": float(chi2), "p": float(p),
                "significant": bool(p < 0.05), "note": ""}
    except Exception as exc:
        return {"statistic": None, "p": None, "note": str(exc)}


def kmo_test(X: pd.DataFrame) -> dict:
    """Kaiser-Meyer-Olkin measure of sampling adequacy."""
    try:
        from factor_analyzer.factor_analyzer import calculate_kmo

        kmo_per_item, kmo_total = calculate_kmo(
            X.select_dtypes(include=[np.number]).dropna())
        kmo_total = float(kmo_total)
        if kmo_total >= 0.9:
            rating = "marvelous"
        elif kmo_total >= 0.8:
            rating = "meritorious"
        elif kmo_total >= 0.7:
            rating = "great"
        elif kmo_total >= 0.6:
            rating = "middling"
        elif kmo_total >= 0.5:
            rating = "mediocre"
        else:
            rating = "miserable"
        return {
            "kmo_total": kmo_total, "rating": rating,
            "kmo_per_item": {str(k): float(v) for k, v in kmo_per_item.items()},
            "adequate": bool(kmo_total >= 0.5), "note": "",
        }
    except Exception as exc:
        return {"kmo_total": None, "rating": "unknown",
                "kmo_per_item": {}, "adequate": False, "note": str(exc)}



