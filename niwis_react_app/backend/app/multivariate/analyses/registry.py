"""
Registry of all available multivariate analysis methods.

Each entry maps a canonical method id -> analysis class.  Importing is done
lazily inside :func:`get_analysis` to keep module import costs low and avoid
circular imports.
"""
from __future__ import annotations

from typing import Dict, List, Type

# (method_id, category, display_name) - declared up-front so the frontend can
# build the analysis-selection tree without instantiating engines.
METHOD_REGISTRY: List[dict] = [
    {"id": "regression",        "category": "Regression",            "name": "Multiple Regression"},
    {"id": "manova",            "category": "Multivariate Hypothesis Testing", "name": "MANOVA"},
    {"id": "pca",               "category": "Dimension Reduction",   "name": "Principal Component Analysis"},
    {"id": "factor",            "category": "Dimension Reduction",   "name": "Factor Analysis"},
    {"id": "cluster",           "category": "Clustering",            "name": "Cluster Analysis"},
    {"id": "discriminant",      "category": "Classification",        "name": "Discriminant Analysis"},
    {"id": "correspondence",    "category": "Categorical Data",      "name": "Correspondence Analysis"},
    {"id": "ica",               "category": "Dimension Reduction",   "name": "Independent Component Analysis"},
    {"id": "pls",               "category": "Prediction",            "name": "Partial Least Squares"},
    {"id": "mds",               "category": "Similarity / Distance", "name": "Multidimensional Scaling"},
    {"id": "canonical",         "category": "Relationships",         "name": "Canonical Correlation"},
]

# Lazy class path map (full dotted paths from project root)
_CLASS_PATHS = {
    "regression": "app.multivariate.analyses.regression.MultipleRegression",
    "manova": "app.multivariate.analyses.additional.MANOVAAnalysis",
    "pca": "app.multivariate.analyses.pca.PrincipalComponentAnalysis",
    "factor": "app.multivariate.analyses.additional.FactorAnalysisEngine",
    "cluster": "app.multivariate.analyses.clustering.ClusterAnalysis",
    "discriminant": "app.multivariate.analyses.additional.DiscriminantAnalysis",
    "correspondence": "app.multivariate.analyses.additional.CorrespondenceAnalysis",
    "ica": "app.multivariate.analyses.additional.IndependentComponentAnalysis",
    "pls": "app.multivariate.analyses.additional.PartialLeastSquares",
    "mds": "app.multivariate.analyses.additional.MultidimensionalScaling",
    "canonical": "app.multivariate.analyses.additional.CanonicalCorrelation",
}


def get_analysis(method_id: str, dataset_engine):
    """Instantiate the analysis engine for ``method_id``."""
    from importlib import import_module
    import os
    import sys

    if method_id not in _CLASS_PATHS:
        raise ValueError(f"Unknown analysis method: {method_id}")

    # Ensure the project root is on sys.path so ``backend.src`` is importable
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    module_path, cls_name = _CLASS_PATHS[method_id].rsplit(".", 1)
    mod = import_module(module_path)
    cls = getattr(mod, cls_name)
    return cls(dataset_engine)


def list_methods() -> List[dict]:
    """Return the static method catalogue for the frontend."""
    return [dict(m) for m in METHOD_REGISTRY]

