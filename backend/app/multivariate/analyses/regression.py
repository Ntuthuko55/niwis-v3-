"""
Multiple Regression analysis engine.

Implements:
  * assumption & applicability checks (multicollinearity via VIF, sample size)
  * OLS estimation with statsmodels
  * coefficient table with VIF, t-stats, p-values, confidence intervals
  * model summary statistics
  * diagnostic plots (residuals vs fitted, Q-Q, histogram, scale-location,
    leverage, Cook's distance)
  * heteroscedasticity & normality tests
  * automatic interpretation + reproducible Python code
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor, OLSInfluence

from ..core.assumptions import AssumptionResult, PreconditionCheck, summarize_assumptions
from ..utils import AnalysisResult, plot_to_json, table_to_records, _to_jsonable
from .base import BaseAnalysis


class MultipleRegression(BaseAnalysis):
    name = "Multiple Regression"
    category = "Regression"
    tags = ["regression", "linear", "continuous-outcome"]

    _purpose_text = (
        "Multiple regression models a continuous dependent variable as a linear "
        "combination of predictor variables plus an error term."
    )
    _purpose_latex = (
        r"Y = \beta_0 + \beta_1 X_1 + \beta_2 X_2 + \cdots + \beta_p X_p + \epsilon"
    )

    def run_analysis(self, df: pd.DataFrame, config: dict,
                     type_map: Optional[Dict[str, str]] = None) -> AnalysisResult:
        dep = config.get("dependent_variable")
        indep = config.get("independent_variables") or []
        if not dep or not indep:
            res = self._empty_result()
            res.applicable = False
            res.errors.append("Please select one dependent variable and at least "
                              "one predictor variable.")
            return res

        result = AnalysisResult(
            method=self.name, category=self.category,
            purpose=self._purpose_text, purpose_latex=self._purpose_latex,
        )
        result.user_config = config
        result.data_used = {
            "total_observations": int(len(df)),
            "dependent_variable": str(dep),
            "predictor_variables": list(indep),
        }

        types_map = self.engine.get_column_types(df)
        if type_map:
            types_map.update(type_map)
        cat_preds = [c for c in indep
                     if types_map.get(c, "") in ("categorical", "ordinal", "binary")]
        num_preds = [c for c in indep if c not in cat_preds]

        predictors_df = df[indep].copy()
        pre: List[str] = []
        for c in num_preds:
            predictors_df[c] = pd.to_numeric(predictors_df[c], errors="coerce")
        if cat_preds:
            pre.append("Categorical predictors encoded via dummy variables "
                       "(drop-first) to avoid the dummy-variable trap.")
            encoded = pd.get_dummies(predictors_df[cat_preds], drop_first=True, dtype=float)
            predictors_df = pd.concat(
                [predictors_df[num_preds].astype(float), encoded], axis=1
            )
        pre.append("Missing observations in the selected variables removed "
                   "listwise before estimation.")

        y = pd.to_numeric(df[dep], errors="coerce")
        X_raw = predictors_df.astype(float)
        data = pd.concat([y.rename("DEP"), X_raw], axis=1).dropna()
        n_obs = len(data)
        y_clean = data["DEP"]
        X_clean = data.drop(columns=["DEP"])

        result.preprocessing = pre
        result.data_used["observations_used"] = int(n_obs)
        result.data_used["predictors_selected"] = list(X_clean.columns)

        checks: List[PreconditionCheck] = []
        n_params = X_clean.shape[1] + 1
        self._sample_size_check(checks, n_obs, len(indep))
        if n_obs - X_clean.shape[1] - 1 < 1:
            checks.append(PreconditionCheck(
                "Degrees of freedom", "fail",
                "More predictors than observations after encoding."))
        result.preconditions = [c.to_dict() for c in checks]
        result.applicable = all(c.status != "fail" for c in checks)

        if not result.applicable:
            result.interpretation = ("Multiple regression could not be performed "
                                     "because preconditions failed. See list.")
            result.limitations = ["Review failed preconditions before re-running."]
            self._add_code(result, _regression_code(
                dep, indep, cat_preds, num_preds, list(X_clean.columns)))
            return result

        self._check_assumptions(result, X_clean, y_clean, n_obs)
        X_design = sm.add_constant(X_clean, has_constant="add")
        try:
            model = sm.OLS(y_clean, X_design).fit()
        except Exception as exc:
            result.errors.append(f"OLS estimation failed: {exc}")
            return result
        self._populate_results(result, model, X_clean, X_design, y_clean, n_obs)
        self._build_visualizations(result, model, X_clean, y_clean)
        self._build_interpretation(result, model, X_clean)
        self._add_code(result, _regression_code(
            dep, indep, cat_preds, num_preds, list(X_clean.columns)))
        return result
    # ------------------------------------------------------------------
    def _sample_size_check(self, checks, n_obs, n_pred):
        if n_obs < 20:
            checks.append(PreconditionCheck(
                "Minimum sample size", "fail",
                f"Only {n_obs} complete observations. At least 20 are recommended."))
        elif n_obs < 50 * max(n_pred, 1):
            checks.append(PreconditionCheck(
                "Minimum sample size", "warning",
                f"{n_obs} complete observations for {n_pred} predictors."))
        else:
            checks.append(PreconditionCheck(
                "Minimum sample size", "pass",
                f"{n_obs} complete observations with {n_pred} predictors."))

    # ------------------------------------------------------------------
    def _check_assumptions(self, result, X, y, n_obs):
        assumptions: List[AssumptionResult] = []
        # Linearity proxy
        lin_corrs = {}
        for c in X.columns:
            if np.std(X[c]) == 0 or np.std(y) == 0:
                continue
            r = np.corrcoef(X[c].astype(float).values, y.values)[0, 1]
            if np.isfinite(r):
                lin_corrs[c] = float(r)
        strongest = max((abs(v) for v in lin_corrs.values()), default=0.0)
        assumptions.append(AssumptionResult(
            "Linearity", "pass" if strongest > 0.1 else "warning",
            f"Strongest absolute correlation between a predictor and the outcome "
            f"is {strongest:.3f}. Inspect residual plots for non-linearity."))

        # Multicollinearity via VIF
        vif_vals = []
        if X.shape[1] >= 2 and not X.empty:
            for i, col in enumerate(X.columns):
                try:
                    v = float(variance_inflation_factor(X.values, i))
                except Exception:
                    v = float("nan")
                vif_vals.append({"predictor": col, "VIF": v})
            valid_vifs = [v["VIF"] for v in vif_vals if not np.isnan(v["VIF"])]
            max_vif = max(valid_vifs) if valid_vifs else 0.0
            if max_vif >= 10:
                assumptions.append(AssumptionResult(
                    "No severe multicollinearity", "fail",
                    f"Maximum VIF = {max_vif:.2f} (>=10 indicates severe multicollinearity)."))
            elif max_vif >= 5:
                assumptions.append(AssumptionResult(
                    "No severe multicollinearity", "warning",
                    f"Maximum VIF = {max_vif:.2f} (>=5 indicates moderate multicollinearity)."))
            else:
                assumptions.append(AssumptionResult(
                    "No severe multicollinearity", "pass",
                    f"Maximum VIF = {max_vif:.2f} (<5, acceptable)."))
        else:
            assumptions.append(AssumptionResult(
                "No severe multicollinearity", "pass",
                "Single predictor - multicollinearity not applicable."))
        result.results["vif_table"] = vif_vals

        n_params = X.shape[1] + 1
        ratio = n_obs / max(n_params, 1)
        if ratio < 10:
            assumptions.append(AssumptionResult(
                "Observations per parameter", "fail",
                f"Ratio = {ratio:.1f} (recommended >= 10)."))
        elif ratio < 15:
            assumptions.append(AssumptionResult(
                "Observations per parameter", "warning",
                f"Ratio = {ratio:.1f} (recommended >= 15)."))
        else:
            assumptions.append(AssumptionResult(
                "Observations per parameter", "pass",
                f"Ratio = {ratio:.1f} observations per parameter."))

        result.assumptions = [a.to_dict() for a in assumptions]
        result.assumption_summary = summarize_assumptions(assumptions)

    # ------------------------------------------------------------------ results
    def _populate_results(self, result, model, X, X_design, y, n_obs):
        params, bse = model.params, model.bse
        tvals, pvals = model.tvalues, model.pvalues
        conf = model.conf_int()
        coef_rows = []
        for name in X_design.columns:
            coef_rows.append({
                "variable": name,
                "coefficient": float(params[name]),
                "std_error": float(bse[name]),
                "t": float(tvals[name]),
                "p_value": float(pvals[name]),
                "ci_lower": float(conf.loc[name, 0]),
                "ci_upper": float(conf.loc[name, 1]),
            })

        resid = model.resid
        y_pred = model.fittedvalues
        n = n_obs
        k = X.shape[1] + 1
        rmse = float(np.sqrt(np.sum(resid ** 2) / (n - k)))
        mae = float(np.mean(np.abs(resid)))

        result.results["model_summary"] = {
            "r_squared": float(model.rsquared),
            "adj_r_squared": float(model.rsquared_adj),
            "f_statistic": float(model.fvalue),
            "f_pvalue": float(model.f_pvalue),
            "rmse": rmse, "mae": mae,
            "n_observations": int(n), "n_predictors": int(X.shape[1]),
            "df_residual": int(model.df_resid),
            "aic": float(model.aic), "bic": float(model.bic),
        }
        result.tables.append({
            "name": "Coefficient Table",
            "description": "Estimated regression coefficients with 95% CI.",
            "columns": ["variable", "coefficient", "std_error", "t", "p_value",
                        "ci_lower", "ci_upper"],
            "rows": coef_rows,
        })
        result.results["residuals"] = _to_jsonable(
            {"fitted": y_pred.values.tolist(),
             "resid": resid.values.tolist(),
             "studentized": (resid / np.std(resid, ddof=1)).values.tolist()})
        diag = {}
        try:
            bp_lm, bp_p, bp_f, bp_f_p = het_breuschpagan(resid.values, X_design.values)
            diag["breusch_pagan"] = {"lm": float(bp_lm), "lm_p": float(bp_p),
                                     "f": float(bp_f), "f_p": float(bp_f_p),
                                     "heteroscedastic": bool(bp_p < 0.05)}
        except Exception as exc:
            diag["breusch_pagan"] = {"error": str(exc)}
        try:
            wb = sm.stats.jarque_bera(resid.values)
            diag["jarque_bera"] = {"statistic": float(wb[0]), "p": float(wb[1]),
                                   "skew": float(wb[2]), "kurtosis": float(wb[3]),
                                   "normal": bool(wb[1] > 0.05)}
        except Exception as exc:
            diag["jarque_bera"] = {"error": str(exc)}
        try:
            sw = stats.shapiro(resid.values)
            diag["shapiro_wilk"] = {"statistic": float(sw.statistic),
                                    "p": float(sw.pvalue),
                                    "normal": bool(sw.pvalue > 0.05)}
        except Exception as exc:
            diag["shapiro_wilk"] = {"error": str(exc)}
        result.results["diagnostics"] = diag

    # ------------------------------------------------------------------ viz
    def _build_visualizations(self, result, model, X, y):
        resid = model.resid
        fitted = model.fittedvalues
        infl = OLSInfluence(model)
        leverage = infl.hat_matrix_diag
        cooks = infl.cooks_distance[0]

        fig1 = px.scatter(x=fitted.values, y=resid.values,
                          labels={"x": "Fitted values", "y": "Residuals"},
                          title="Residuals vs Fitted")
        fig1.add_hline(y=0, line_dash="dash", line_color="red")
        result.visualizations.append({"id": "resid_fitted", "title": "Residuals vs Fitted",
                                      "type": "scatter", "spec": plot_to_json(fig1)})

        fig2 = go.Figure()
        theoretical = np.sort(stats.norm.ppf(
            (np.arange(1, len(resid) + 1) - 0.5) / len(resid)))
        ordered = np.sort(resid.values)
        fig2.add_trace(go.Scatter(x=theoretical, y=ordered, mode="markers",
                                  name="Sample", showlegend=False))
        slope, intercept = np.polyfit(theoretical, ordered, 1)
        fig2.add_trace(go.Scatter(x=theoretical, y=slope * theoretical + intercept,
                                  mode="lines", name="Theoretical normal",
                                  line=dict(color="red")))
        fig2.update_layout(title="Normal Q-Q Plot of Residuals",
                           xaxis_title="Theoretical Quantiles",
                           yaxis_title="Sample Quantiles")
        result.visualizations.append({"id": "qq", "title": "Q-Q Plot",
                                      "type": "qq", "spec": plot_to_json(fig2)})

        fig3 = px.histogram(x=resid.values, nbins=30,
                            labels={"x": "Residuals"}, title="Residual Distribution")
        fig3.update_layout(yaxis_title="Count")
        result.visualizations.append({"id": "resid_hist", "title": "Residual Histogram",
                                      "type": "histogram", "spec": plot_to_json(fig3)})

        std_resid = resid / np.std(resid, ddof=1)
        fig4 = px.scatter(x=fitted.values, y=np.sqrt(np.abs(std_resid)),
                          labels={"x": "Fitted values",
                                  "y": "\u221a|Standardized Residuals|"},
                          title="Scale-Location")
        result.visualizations.append({"id": "scale_loc", "title": "Scale-Location",
                                      "type": "scatter", "spec": plot_to_json(fig4)})

        fig5 = px.scatter(x=leverage, y=resid.values,
                          labels={"x": "Leverage", "y": "Residuals"},
                          title="Residuals vs Leverage")
        result.visualizations.append({"id": "leverage", "title": "Residuals vs Leverage",
                                      "type": "scatter", "spec": plot_to_json(fig5)})

        fig6 = go.Figure()
        idx = np.arange(len(cooks))
        fig6.add_trace(go.Bar(x=idx, y=cooks, name="Cook's distance"))
        thr = 4.0 / len(cooks) if len(cooks) else 0.0
        fig6.add_hline(y=thr, line_dash="dash", line_color="red",
                       annotation_text=f"4/n = {thr:.4f}")
        fig6.update_layout(title="Cook's Distance",
                           xaxis_title="Observation index",
                           yaxis_title="Cook's distance")
        result.visualizations.append({"id": "cooks", "title": "Cook's Distance",
                                      "type": "bar", "spec": plot_to_json(fig6)})

    # ------------------------------------------------------------------ interp
    def _build_interpretation(self, result, model, X):
        summ = result.results["model_summary"]
        rows = result.tables[0]["rows"] if result.tables else []
        sig = [r for r in rows
               if r["p_value"] < 0.05 and r["variable"] != "const"]
        r2 = summ["r_squared"]
        interp = (
            f"The multiple regression model explains **{r2 * 100:.1f}%** of the "
            f"variance in the dependent variable "
            f"({result.user_config.get('dependent_variable')}). "
            f"The overall model is "
            f"{'statistically significant' if summ['f_pvalue'] < 0.05 else 'not statistically significant'} "
            f"(F = {summ['f_statistic']:.2f}, p = {summ['f_pvalue']:.4f}). ")
        if sig:
            names = ", ".join(
                f"{r['variable']} (\u03b2={r['coefficient']:.3f}, p={r['p_value']:.3f})"
                for r in sig[:3])
            interp += (f"The following predictors are significant at \u03b1=0.05: "
                       f"{names}. ")
        else:
            interp += "No predictor reached significance at \u03b1=0.05. "
        interp += ("Model fit: RMSE = "
                   f"{summ['rmse']:.3f}, MAE = {summ['mae']:.3f}. "
                   "Coefficients represent the expected change in the outcome "
                   "per unit change in the predictor, holding others constant.")
        result.interpretation = interp
        result.limitations = [
            "Regression assumes linearity; non-linear patterns may be missed.",
            "Outliers and influential observations can disproportionately affect estimates.",
            "Correlational/descriptive unless the data come from a causal design.",
            "Check the VIF table and residual diagnostics before trusting inference.",
        ]


# ---------------------------------------------------------------------- code gen
def _regression_code(dep, indep, cat_preds, num_preds, encoded_cols):
    dummies_line = (
        f"X = pd.get_dummies(data[[{', '.join(repr(c) for c in indep)}]], "
        f"columns={cat_preds!r}, drop_first=True, dtype=float)\n"
    ) if cat_preds else ""
    src = f"""import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.diagnostic import het_breuschpagan

data = pd.read_csv('your_dataset.csv')
y = data[{dep!r}].astype(float)
{dummies_line}if not {bool(cat_preds)}:
    X = data[[{', '.join(repr(c) for c in indep)}]].astype(float)
X = sm.add_constant(X, has_constant='add')
model = sm.OLS(y, X).fit()
print(model.summary())
# Variance Inflation Factors
for i, c in enumerate(X.columns):
    if c == 'const':
        continue
    print(c, variance_inflation_factor(X.values, i))
# Breusch-Pagan test for heteroscedasticity
bp = het_breuschpagan(model.resid, model.model.exog)
print('BP LM p =', bp[1])
# Predicted vs actual
pred = model.predict(X)
"""
    return src



