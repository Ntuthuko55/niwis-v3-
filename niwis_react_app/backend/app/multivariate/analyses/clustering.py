"""Cluster Analysis engine.

Supports five algorithms: K-Means, Hierarchical, DBSCAN, Gaussian Mixture
and K-Medoids (a lightweight PAM implementation).  Provides cluster sizes,
cluster profiles, internal validation metrics (silhouette, Calinski-Harabasz,
Davies-Bouldin) and interactive visualisations (PCA scatter, dendrogram,
silhouette plot, cluster heatmap).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (silhouette_score, silhouette_samples,
                             calinski_harabasz_score, davies_bouldin_score)

from ..core.assumptions import AssumptionResult, PreconditionCheck, summarize_assumptions
from ..utils import AnalysisResult, plot_to_json, _to_jsonable
from .base import BaseAnalysis


class ClusterAnalysis(BaseAnalysis):
    name = "Cluster Analysis"
    category = "Clustering"
    tags = ["clustering", "unsupervised", "segmentation"]
    _purpose_text = ("Cluster analysis groups observations into homogeneous "
                     "sets (clusters) so that within-group similarity is maximised "
                     "and between-group similarity is minimised.")
    _purpose_latex = r"J = \sum_{i=1}^{n} |x_i - \mu_{c_i}|^2"
    ALGORITHMS = ["kmeans", "hierarchical", "dbscan", "gmm", "kmedoids"]

    def run_analysis(self, df, config, type_map=None):
        selected = config.get("variables") or []
        algo = (config.get("algorithm") or "kmeans").lower()
        n_clusters = int(config.get("n_clusters", 3))
        scale = config.get("scale", True)
        if not selected:
            res = self._empty_result()
            res.applicable = False
            res.errors.append("Select at least two numeric variables.")
            return res
        if algo not in self.ALGORITHMS:
            res = self._empty_result()
            res.applicable = False
            res.errors.append(f"Unknown algorithm '{algo}'.")
            return res

        result = AnalysisResult(method=self.name, category=self.category,
                                purpose=self._purpose_text,
                                purpose_latex=self._purpose_latex)
        result.user_config = config
        result.data_used = {"variables": list(selected), "n_raw": int(len(df)),
                            "algorithm": algo, "n_clusters": n_clusters}

        pre: List[str] = []
        mat = df[selected].apply(pd.to_numeric, errors="coerce").dropna()
        n_obs = len(mat)
        result.preprocessing = pre
        result.data_used["observations"] = int(n_obs)

        checks: List[PreconditionCheck] = []
        if mat.shape[1] < 2:
            checks.append(PreconditionCheck("Multiple variables", "fail",
                "Clustering needs at least 2 numeric variables."))
        if n_obs < 10:
            checks.append(PreconditionCheck("Sample size", "fail",
                f"Only {n_obs} observations (need >= 10)."))
        elif n_obs < mat.shape[1] * 5:
            checks.append(PreconditionCheck("Sample size", "warning",
                f"Only {n_obs} obs for {mat.shape[1]} variables."))
        result.preconditions = [c.to_dict() for c in checks]
        result.applicable = all(c.status != "fail" for c in checks)
        if not result.applicable:
            result.interpretation = "Clustering could not be performed: preconditions failed."
            result.limitations = ["Fix preconditions and retry."]
            self._add_code(result, _cluster_code(selected, algo, n_clusters, scale))
            return result

        if scale:
            pre.append("Variables standardised to unit variance for Euclidean distance.")
            X = StandardScaler().fit_transform(mat.values)
        else:
            pre.append("Variables used in original units.")
            X = mat.values.astype(float)
        result.preprocessing = pre

        assumptions = [
            AssumptionResult("Distance-based clustering", "pass",
                             "Euclidean distance used (standardisation applied).")
            if scale else AssumptionResult("Distance-based clustering", "warning",
                "Standardisation disabled; variables on different scales may dominate."),
            AssumptionResult("Sufficient sample size",
                             "pass" if n_obs >= 5 * mat.shape[1] else "warning",
                             f"{n_obs} observations, {mat.shape[1]} variables."),
        ]
        result.assumptions = [a.to_dict() for a in assumptions]
        result.assumption_summary = summarize_assumptions(assumptions)

        labels, extra = self._run_algorithm(algo, X, n_clusters, config)
        if labels is None:
            result.errors.append("Algorithm failed to produce a clustering.")
            return result
        self._build_clusters(result, mat, labels, extra)
        self._build_metrics(result, X, labels)
        self._visualize(result, X, mat, labels, algo, extra)
        self._interpret(result, algo, labels, n_obs, mat)
        self._add_code(result, _cluster_code(selected, algo, n_clusters, scale))
        return result

    # ------------------------------------------------------------------ algo
    def _run_algorithm(self, algo, X, n_clusters, config):
        if algo == "kmeans":
            km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
            labels = km.fit_predict(X)
            return labels, {"inertia": float(km.inertia_),
                            "centers": km.cluster_centers_.tolist()}
        if algo == "hierarchical":
            method = config.get("linkage", "ward")
            Z = linkage(X, method=method)
            labels = fcluster(Z, t=n_clusters, criterion="maxclust") - 1
            return labels, {"linkage": method, "Z": Z.tolist()}
        if algo == "dbscan":
            eps = float(config.get("eps", 0.5))
            min_samples = int(config.get("min_samples", max(5, X.shape[1] + 1)))
            db = DBSCAN(eps=eps, min_samples=min_samples)
            labels = db.fit_predict(X)
            return labels, {"eps": eps, "min_samples": min_samples,
                            "n_noise": int((labels == -1).sum())}
        if algo == "gmm":
            gmm = GaussianMixture(n_components=n_clusters, random_state=42, n_init=10)
            labels = gmm.fit_predict(X)
            return labels, {"bic": float(gmm.bic(X)), "aic": float(gmm.aic(X))}
        if algo == "kmedoids":
            labels, centers = _kmedoids(X, n_clusters, config.get("max_iter", 100))
            return labels, {"centers": centers.tolist()}
        return None, {}

    # ------------------------------------------------------------------ clusters
    def _build_clusters(self, result, mat, labels, extra):
        mat = mat.copy()
        mat["__cluster__"] = labels
        n_clusters = len([l for l in np.unique(labels) if l != -1])
        sizes = mat.groupby("__cluster__").size().to_dict()
        result.results["cluster_sizes"] = _to_jsonable(
            {str(k): int(v) for k, v in sizes.items()})
        result.results["extra"] = _to_jsonable(extra)

        # cluster profiles (mean of each variable per cluster)
        profile = mat.groupby("__cluster__").mean(numeric_only=True).round(3)
        result.results["cluster_profiles"] = _to_jsonable(profile)
        # cluster centres table
        if n_clusters > 0:
            prof_df = mat.groupby("__cluster__").mean(numeric_only=True)
            rows = [{"cluster": idx, **{c: float(prof_df.loc[idx, c])
                                        for c in prof_df.columns}}
                    for idx in prof_df.index]
            result.tables.append({
                "name": "Cluster Profiles (means)",
                "description": "Mean value of each variable within each cluster.",
                "columns": ["cluster"] + list(profile.columns),
                "rows": rows,
            })
        result.results["labels"] = labels.tolist()

    # ------------------------------------------------------------------ metrics
    def _build_metrics(self, result, X, labels):
        metrics: Dict[str, float] = {}
        valid = labels != -1
        n_unique = len(np.unique(labels[valid])) if valid.any() else 0
        if n_unique >= 2 and valid.sum() > n_unique:
            try:
                metrics["silhouette"] = float(silhouette_score(X[valid], labels[valid]))
            except Exception:
                metrics["silhouette"] = None
            try:
                metrics["calinski_harabasz"] = float(
                    calinski_harabasz_score(X[valid], labels[valid]))
            except Exception:
                metrics["calinski_harabasz"] = None
            try:
                metrics["davies_bouldin"] = float(
                    davies_bouldin_score(X[valid], labels[valid]))
            except Exception:
                metrics["davies_bouldin"] = None
        else:
            metrics["note"] = "Internal metrics require >= 2 non-noise clusters."
        # elbow suggestion: run k-means for k=1..min(10,n-1) and find max delta
        if n_unique >= 2:
            inertias = []
            ks = list(range(1, min(11, len(X) - 1)))
            for k in ks:
                try:
                    km = KMeans(n_clusters=k, n_init=5, random_state=42).fit(X)
                    inertias.append(float(km.inertia_))
                except Exception:
                    inertias.append(None)
            result.results["elbow"] = _to_jsonable(
                {"k_values": ks, "inertia": inertias})
        result.results["metrics"] = metrics

    # ------------------------------------------------------------------ viz
    def _visualize(self, result, X, mat, labels, algo, extra):
        n_clusters = len([l for l in np.unique(labels) if l != -1])
        n_comp = min(2, min(X.shape)) if X.shape[0] > 1 else 1
        pca = PCA(n_components=n_comp) if X.shape[1] >= 2 else None
        if pca is not None:
            comp = pca.fit_transform(X)
        else:
            comp = X[:, :2] if X.shape[1] >= 2 else np.zeros((X.shape[0], 2))

        # PCA cluster scatter
        fig = px.scatter(x=comp[:, 0], y=comp[:, 1],
                         color=[str(l) if l != -1 else "noise" for l in labels],
                         title=f"Cluster Scatter (PCA, {algo})",
                         labels={"x": "PC1", "y": "PC2"})
        fig.update_layout(legend_title_text="Cluster")
        result.visualizations.append({"id": "pca_scatter", "title": "PCA Cluster Scatter",
                                      "type": "scatter", "spec": plot_to_json(fig)})

        # silhouette plot (for non-DBSCAN and >=2 clusters)
        if algo != "dbscan" and n_clusters >= 2:
            valid = labels != -1
            sil = silhouette_samples(X[valid], labels[valid])
            order = np.argsort(labels[valid])
            fig2 = go.Figure()
            y_low = 0
            for c, lab in enumerate(np.unique(labels[valid])):
                vals = np.sort(sil[labels[valid] == lab])
                ys = np.arange(y_low, y_low + len(vals))
                fig2.add_trace(go.Bar(y=ys.tolist(),
                                      x=vals.tolist(), name=f"Cluster {lab}",
                                      orientation="h"))
                y_low += len(vals)
            fig2.add_vline(x=float(np.mean(sil)), line_dash="dash",
                           annotation_text="mean silhouette")
            fig2.update_layout(title="Silhouette Plot",
                               xaxis_title="Silhouette coefficient",
                               yaxis_title="Observation")
            result.visualizations.append({"id": "silhouette", "title": "Silhouette Plot",
                                          "type": "bar", "spec": plot_to_json(fig2)})

        # dendrogram (hierarchical only)
        if algo == "hierarchical" and "Z" in extra:
            fig3 = go.Figure()
            from scipy.cluster.hierarchy import dendrogram as sdend
            counts = {}

            # build a dendrogram with limited leaves for display
            Z = np.array(extra["Z"])
            try:
                ddata = sdend(Z, p=min(30, len(Z) + 1), truncate_mode="level",
                              max_level=3)
                fig3 = _dendrogram_figure(ddata)
                result.visualizations.append({"id": "dendrogram",
                                              "title": "Dendrogram",
                                              "type": "dendrogram",
                                              "spec": plot_to_json(fig3)})
            except Exception as exc:
                result.warnings.append(f"Dendrogram display skipped: {exc}")

        # elbow plot (kmeans)
        if "elbow" in result.results and result.results["elbow"].get("inertia"):
            eb = result.results["elbow"]
            fig4 = go.Figure(go.Scatter(x=eb["k_values"], y=eb["inertia"],
                                     mode="lines+markers", name="Inertia"))
            fig4.update_layout(title="Elbow Method", xaxis_title="k",
                               yaxis_title="Inertia (WCSS)")
            result.visualizations.append({"id": "elbow", "title": "Elbow Method",
                                          "type": "line", "spec": plot_to_json(fig4)})

    def _interpret(self, result, algo, labels, n_obs, mat):
        n_clusters = len([l for l in np.unique(labels) if l != -1])
        n_noise = int((labels == -1).sum())
        m = result.results.get("metrics", {})
        sil = m.get("silhouette")
        msg = (f"The {algo} algorithm identified {n_clusters} cluster(s) "
               f"from {n_obs} observations on {len(mat.columns)} variables. ")
        if algo == "dbscan" and n_noise:
            msg += f"{n_noise} point(s) were labelled as noise (outliers). "
        if sil is not None:
            strength = ("strong" if sil >= 0.7 else "reasonable"
                        if sil >= 0.5 else "weak" if sil >= 0.25 else "no substantial")
            msg += f"Silhouette = {sil:.3f} indicating {strength} structure. "
        else:
            msg += m.get("note", "")
        msg += "Inspect the cluster profiles table to understand each group."
        result.interpretation = msg
        result.limitations = [
            "The number of clusters is sensitive to algorithm choice and parameters.",
            "Cluster labels have no inherent meaning; validate against external criteria.",
            "Standardisation affects distance-based results; review scaling choices.",
        ]



def _dendrogram_figure(ddata):
    """Convert scipy dendrogram dict into a Plotly figure."""
    fig = go.Figure()
    icoord = ddata.get("icoord", [])
    dcoord = ddata.get("dcoord", [])
    colors = ddata.get("color_list", ["blue"] * len(icoord))
    for xs, ys, color in zip(icoord, dcoord, colors):
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines",
                                 line=dict(color=color), showlegend=False))
    fig.update_layout(title="Hierarchical Clustering Dendrogram",
                      xaxis_title="Observation", yaxis_title="Distance")
    return fig


def _kmedoids(X, k, max_iter=100):
    """Simple PAM-style K-Medoids using Euclidean distance."""
    from scipy.spatial.distance import cdist

    n = X.shape[0]
    if k >= n:
        k = n
    rng = np.random.default_rng(42)
    medoids = rng.choice(n, size=k, replace=False)
    for _ in range(max_iter):
        dists = cdist(X, X[medoids])
        labels = np.argmin(dists, axis=1)
        new_medoids = medoids.copy()
        for j in range(k):
            cluster_idx = np.where(labels == j)[0]
            if len(cluster_idx) == 0:
                continue
            in_dists = cdist(X[cluster_idx], X[cluster_idx])
            total = in_dists.sum(axis=1)
            best = cluster_idx[np.argmin(total)]
            new_medoids[j] = best
        if np.array_equal(medoids, new_medoids):
            break
        medoids = new_medoids
    dists = cdist(X, X[medoids])
    labels = np.argmin(dists, axis=1)
    return labels, X[medoids]


def _cluster_code(selected, algo, n_clusters, scale):
    cols_repr = ", ".join(repr(c) for c in selected)
    scale_blk = "StandardScaler().fit_transform(X)\n" if scale else "X"
    algo_blk = {
        "kmeans": "KMeans(n_clusters=N, n_init=10, random_state=42).fit_predict(X)",
        "hierarchical": "from scipy.cluster.hierarchy import linkage, fcluster\n"
                        "Z = linkage(X, method='ward')\n"
                        "labels = fcluster(Z, t=N, criterion='maxclust') - 1",
        "gmm": "GaussianMixture(n_components=N, random_state=42).fit_predict(X)",
        "dbscan": "DBSCAN(eps=0.5, min_samples=5).fit_predict(X)",
        "kmedoids": "labels = _kmedoids(X, N)[0]",
    }[algo]
    blk = algo_blk.replace("N", str(n_clusters))
    if algo == "hierarchical":
        algo_line = blk
    else:
        algo_line = "labels = " + blk
    return (
        "import pandas as pd\nfrom sklearn.preprocessing import StandardScaler\n"
        "from sklearn.cluster import KMeans, DBSCAN\n"
        "from sklearn.mixture import GaussianMixture\n"
        "from sklearn.decomposition import PCA\nimport plotly.express as px\n"
        "data = pd.read_csv('your_dataset.csv')\n"
        f"X = data[[{cols_repr}]].apply(pd.to_numeric, errors='coerce').dropna()\n"
        f"Xs = {scale_blk}"
        f"{algo_line}\n"
        "print('Cluster sizes:', pd.Series(labels).value_counts())\n"
    )



