"""Principal Component Analysis (PCA) engine.

Handles standardization, eigen-decomposition, explained variance, the
correlation/covariance matrix, Bartlett's test of sphericity, KMO, and a
suite of interactive Plotly visualisations (scree, biplot, loading plot,
score plot, correlation circle, 3-D PCA, contributions).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from ..core.assumptions import AssumptionResult, PreconditionCheck, summarize_assumptions
from ..core.assumptions import bartlett_sphericity, kmo_test
from ..utils import AnalysisResult, plot_to_json, _to_jsonable
from .base import BaseAnalysis


class PrincipalComponentAnalysis(BaseAnalysis):
    name = "Principal Component Analysis"
    category = "Dimension Reduction"
    tags = ["dimension-reduction", "pca", "unsupervised"]
    _purpose_text = ("PCA transforms a set of correlated variables into a smaller "
                     "set of uncorrelated components that capture the maximum variance.")
    _purpose_latex = r"\Sigma v_i = \lambda_i v_i \quad,\quad PC_i = X v_i"

    def run_analysis(self, df, config, type_map=None):
        selected = config.get("variables") or []
        n_components = config.get("n_components")
        scale = config.get("scale", True)
        if not selected:
            res = self._empty_result()
            res.applicable = False
            res.errors.append("Select at least two numeric variables.")
            return res
        result = AnalysisResult(method=self.name, category=self.category,
                                purpose=self._purpose_text,
                                purpose_latex=self._purpose_latex)
        result.user_config = config
        result.data_used = {"variables": list(selected), "n_raw": int(len(df))}
        pre: List[str] = []
        mat = df[selected].apply(pd.to_numeric, errors="coerce").dropna()
        n_obs = len(mat)
        result.data_used["observations"] = int(n_obs)
        result.preprocessing = pre

        checks = []
        if mat.shape[1] < 2:
            checks.append(PreconditionCheck("Multiple variables", "fail",
                "PCA requires at least 2 numeric variables."))
        if n_obs < 10:
            checks.append(PreconditionCheck("Sample size", "fail",
                f"Only {n_obs} complete observations (need >= 10)."))
        elif n_obs < 5 * mat.shape[1]:
            checks.append(PreconditionCheck("Sample size", "warning",
                f"{n_obs} observations for {mat.shape[1]} variables."))
        zero_var = [c for c in mat.columns if mat[c].std(ddof=0) == 0]
        if zero_var:
            checks.append(PreconditionCheck("Variance", "fail",
                f"Zero-variance columns: {zero_var}."))
        result.preconditions = [c.to_dict() for c in checks]
        result.applicable = all(c.status != "fail" for c in checks)
        if not result.applicable:
            result.interpretation = "PCA could not be performed: preconditions failed."
            result.limitations = ["Fix failed preconditions and retry."]
            self._add_code(result, _pca_code(selected, scale, n_components))
            return result
        if scale:
            pre.append("Variables standardised to unit variance (correlation matrix).")
            X = StandardScaler().fit_transform(mat.values)
            cov = np.corrcoef(mat.values, rowvar=False)
            cor_type = "correlation"
        else:
            pre.append("Variables left in original units (covariance matrix).")
            X = mat.values
            cov = np.cov(mat.values, rowvar=False)
            cor_type = "covariance"
        result.preprocessing = pre

        assumptions = []
        bs = bartlett_sphericity(mat)
        assumptions.append(AssumptionResult(
            "Bartlett's test of sphericity",
            "pass" if bs.get("p") and bs["p"] < 0.05 else "warning",
            f"chi2={bs.get('statistic')}, p={bs.get('p')}."))
        kmo = kmo_test(mat)
        kt = kmo.get("kmo_total") or 0
        assumptions.append(AssumptionResult(
            "Kaiser-Meyer-Olkin",
            "pass" if kt >= 0.7 else ("warning" if kt >= 0.5 else "fail"),
            f"KMO = {kt}. {'Adequate' if kmo.get('adequate') else 'Inadequate.'}"))
        assumptions.append(AssumptionResult(
            "Sufficient sample size", "pass" if n_obs >= 5 * mat.shape[1] else "warning",
            f"{n_obs} observations, {mat.shape[1]} variables."))
        result.assumptions = [a.to_dict() for a in assumptions]
        result.assumption_summary = summarize_assumptions(assumptions)

        nc = n_components or min(mat.shape)
        pca = PCA(n_components=nc)
        scores = pca.fit_transform(X)
        loadings = pca.components_.T * np.sqrt(pca.explained_variance_)
        ev_ratio = pca.explained_variance_ratio_
        cum_var = np.cumsum(ev_ratio)
        comp_names = [f"PC{i+1}" for i in range(nc)]
        load_df = pd.DataFrame(loadings, index=mat.columns, columns=comp_names).round(4)
        recommend = int(np.searchsorted(cum_var, 0.8) + 1) if len(cum_var) else 1
        if recommend < 1:
            recommend = 1
        eigen_table = [{"component": comp_names[i],
                        "eigenvalue": float(pca.explained_variance_[i]),
                        "prop_var": float(ev_ratio[i]),
                        "cum_var": float(cum_var[i])} for i in range(nc)]
        result.formula = self._purpose_latex
        result.results.update({
            "correlation_matrix_type": cor_type,
            "eigenvalues": eigen_table,
            "explained_variance": {
                "per_component": [float(e) for e in ev_ratio],
                "cumulative": [float(c) for c in cum_var],
                "recommended_components": int(recommend),
                "recommended_explanation": (
                    f"The first {recommend} component(s) explain "
                    f"{cum_var[min(recommend-1, len(cum_var)-1)]*100:.1f}% "
                    "of the variance (>=80% threshold)."),
            },
            "correlation_matrix": _to_jsonable(cov),
            "matrix_shape": list(cov.shape),
        })
        result.tables.append({
            "name": "Eigenvalues & Variance Explained",
            "description": "Components ordered by decreasing eigenvalue.",
            "columns": ["component", "eigenvalue", "prop_var", "cum_var"],
            "rows": eigen_table,
        })
        result.tables.append({
            "name": "PCA Loadings",
            "description": "Component loadings (eigenvectors scaled by sqrt eigenvalue).",
            "columns": ["variable"] + comp_names,
            "rows": [_to_jsonable({"variable": idx, **{c: row[c] for c in comp_names}})
                     for idx, row in load_df.iterrows()],
        })
        self._visualize(result, mat, scores, loadings, ev_ratio, cum_var,
                        comp_names, recommend)
        self._interpret(result, load_df, ev_ratio, cum_var, recommend, mat)
        self._add_code(result, _pca_code(selected, scale, n_components))
        return result

    # ------------------------------------------------------------------ viz
    def _visualize(self, result, mat, scores, loadings, ev_ratio, cum_var,
                   comp_names, recommend):
        fig = go.Figure(go.Bar(x=comp_names,
                               y=[float(v) for v in ev_ratio], name="Eigenvalue"))
        fig.add_hline(y=1.0, line_dash="dash", line_color="red",
                      annotation_text="Kaiser criterion")
        fig.update_layout(title="Scree Plot", yaxis_title="Eigenvalue",
                          xaxis_title="Component")
        result.visualizations.append({"id": "scree", "title": "Scree Plot",
                                      "type": "bar", "spec": plot_to_json(fig)})

        fig2 = go.Figure(go.Scatter(x=comp_names,
                                    y=[float(v) for v in cum_var],
                                    mode="lines+markers", name="Cumulative"))
        fig2.add_hline(y=0.8, line_dash="dash", line_color="green",
                       annotation_text="80% threshold")
        fig2.update_layout(title="Cumulative Explained Variance",
                           yaxis_title="Cumulative proportion")
        result.visualizations.append({"id": "cumvar", "title": "Cumulative Variance",
                                      "type": "line", "spec": plot_to_json(fig2)})

        load2 = loadings[:, :2]
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=scores[:, 0], y=scores[:, 1],
                                  mode="markers", name="Observations",
                                  marker=dict(size=6, opacity=0.6)))
        for j, var in enumerate(mat.columns):
            fig3.add_annotation(ax=0, ay=0, x=load2[j, 0] * 1.5, y=load2[j, 1] * 1.5,
                                xref="x", yref="y", text=str(var),
                                showarrow=True, arrowhead=2, font=dict(size=10))
        fig3.update_layout(title="PCA Biplot (PC1 vs PC2)",
                           xaxis_title=f"PC1 ({ev_ratio[0]*100:.1f}%)",
                           yaxis_title=f"PC2 ({ev_ratio[1]*100:.1f}%)")
        result.visualizations.append({"id": "biplot", "title": "Biplot",
                                      "type": "scatter", "spec": plot_to_json(fig3)})

        fig4 = go.Figure()
        for j, var in enumerate(mat.columns):
            fig4.add_trace(go.Scatter(x=[load2[j, 0]], y=[load2[j, 1]],
                                      mode="markers+text", text=[var],
                                      textposition="top center", name=var,
                                      showlegend=False))
        fig4.add_trace(go.Scatter(x=[-1.2, 1.2], y=[0, 0], mode="lines",
                                  line=dict(color="grey", dash="dash"),
                                  showlegend=False, hoverinfo="skip"))
        fig4.add_trace(go.Scatter(x=[0, 0], y=[-1.2, 1.2], mode="lines",
                                  line=dict(color="grey", dash="dash"),
                                  showlegend=False, hoverinfo="skip"))
        fig4.update_layout(title="Loading Plot (PC1, PC2)", xaxis_title="PC1",
                           yaxis_title="PC2", xaxis_range=[-1.2, 1.2],
                           yaxis_range=[-1.2, 1.2])
        result.visualizations.append({"id": "loadings", "title": "Loading Plot",
                                      "type": "scatter", "spec": plot_to_json(fig4)})

        fig5 = px.scatter(x=scores[:, 0], y=scores[:, 1], title="Score Plot (PC1 vs PC2)")
        fig5.update_layout(xaxis_title="PC1", yaxis_title="PC2")
        result.visualizations.append({"id": "scores", "title": "Score Plot",
                                      "type": "scatter", "spec": plot_to_json(fig5)})

        if scores.shape[1] >= 3:
            fig6 = px.scatter_3d(x=scores[:, 0], y=scores[:, 1], z=scores[:, 2],
                                 title="3D PCA", labels={"x": "PC1", "y": "PC2", "z": "PC3"})
            fig6.update_layout(scene=dict(
                xaxis_title=f"PC1 ({ev_ratio[0]*100:.1f}%)",
                yaxis_title=f"PC2 ({ev_ratio[1]*100:.1f}%)",
                zaxis_title=f"PC3 ({ev_ratio[2]*100:.1f}%)"))
            result.visualizations.append({"id": "pca3d", "title": "3D PCA",
                                          "type": "scatter3d", "spec": plot_to_json(fig6)})

        contrib = pd.DataFrame(loadings[:, :2] ** 2, index=mat.columns, columns=["PC1", "PC2"])
        fig7 = go.Figure()
        for j, var in enumerate(mat.columns):
            fig7.add_trace(go.Bar(name=str(var), x=["PC1", "PC2"],
                                  y=[contrib.loc[var, "PC1"], contrib.loc[var, "PC2"]]))
        fig7.update_layout(title="Variable Contribution", yaxis_title="Squared loading")
        result.visualizations.append({"id": "contrib", "title": "Variable Contribution",
                                      "type": "bar", "spec": plot_to_json(fig7)})

    def _interpret(self, result, load_df, ev_ratio, cum_var, recommend, mat):
        pc1_var = ev_ratio[0] * 100
        top_vars = load_df.index[np.argsort(-np.abs(load_df.iloc[:, 0]))[:3]].tolist()
        interp = (
            f"PCA was performed on {len(mat.columns)} standardised variables. "
            f"PC1 accounts for **{pc1_var:.1f}%** of the total variance. "
            f"The first {recommend} component(s) explain "
            f"**{cum_var[min(recommend-1, len(cum_var)-1)]*100:.1f}%** "
            f"of the variance (meets the 80% threshold). "
            f"Variables most strongly associated with PC1: "
            f"{', '.join(top_vars)}.")
        result.interpretation = interp
        result.limitations = [
            "PCA is sensitive to the scale of variables; standardisation is "
            "recommended when variables are on different scales.",
            "Components are linear combinations; interpretability depends on the "
            "loading structure.",
            "PCA is unsupervised and ignores any dependent variable.",
        ]



def _pca_code(selected, scale, n_components):
    cols_repr = ', '.join(repr(c) for c in selected)
    if scale:
        scale_block = "Xs = StandardScaler().fit_transform(X)\n"
    else:
        scale_block = "Xs = X.values\n"
    if n_components is not None and isinstance(n_components, int):
        nc_block = f"pca = PCA(n_components={n_components})\n"
    else:
        nc_block = "pca = PCA(n_components=min(X.shape))\n"
    return (
        "import pandas as pd\n"
        "import numpy as np\n"
        "from sklearn.decomposition import PCA\n"
        + ("from sklearn.preprocessing import StandardScaler\n" if scale else "")
        + "\ndata = pd.read_csv('your_dataset.csv')\n"
        f"X = data[[{cols_repr}]].apply(pd.to_numeric, errors='coerce').dropna()\n"
        f"{scale_block}{nc_block}"
        "scores = pca.fit_transform(Xs)\n"
        "print('Explained variance ratio:', pca.explained_variance_ratio_)\n"
        "print('Cumulative:', np.cumsum(pca.explained_variance_ratio_))\n"
        "loadings = pca.components_.T * np.sqrt(pca.explained_variance_)\n"
        "print(pd.DataFrame(loadings, index=X.columns,\n"
        "      columns=[f'PC{i+1}' for i in range(pca.n_components_)]))\n"
    )


