"""Model evaluation - produce a comparison table over a chronological holdout."""
from __future__ import annotations

from typing import Any

from .models import available_models
from .validation import run_validation_split


def compare_models(
    y_train,
    y_val,
    horizon: int,
    models: list[str] | None = None,
) -> dict[str, Any]:
    """Run all candidate models on a single chronological train/val split.

    Returns ``{model: {metrics, status, error, time}}`` where metrics are computed
    out-of-sample on ``y_val`` (never seen during training).
    """
    if models is None:
        models = available_models()
    return run_validation_split(y_train, y_val, horizon, models)


def build_comparison_table(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn the comparison dict into a ready-to-render table.

    Columns: model, mae, rmse, r_squared, mase, training_time, selected.
    """
    rows: list[dict[str, Any]] = []
    valid = {m for m, r in comparison.items() if r.get("status") == "ok"}
    best = min(valid, key=lambda m: comparison[m]["metrics"]["rmse"]) if valid else None
    for model, res in comparison.items():
        row: dict[str, Any] = {"model": model, "status": res.get("status")}
        if res.get("status") == "ok":
            m = res["metrics"]
            row.update({
                "mae": round(m.get("mae", 0.0), 4),
                "rmse": round(m.get("rmse", 0.0), 4),
                "r_squared": round(m.get("r_squared", 0.0), 4),
                "mase": round(m["mase"], 4) if isinstance(m.get("mase"), (int, float)) else None,
                "training_time": res.get("time"),
                "selected": model == best,
            })
        else:
            row.update({"mae": None, "rmse": None, "r_squared": None,
                        "mase": None, "training_time": res.get("time"),
                        "error": res.get("error"), "selected": False})
        rows.append(row)
    return rows


def sort_comparison_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort comparison rows by RMSE ascending, failures last."""
    def key(r):
        if r.get("status") != "ok" or r.get("rmse") is None:
            return (1.0, float("inf"))
        return (0.0, r["rmse"])
    return sorted(rows, key=key)