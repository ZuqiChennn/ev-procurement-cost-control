"""Build procurement marts, risk scores, anomalies and dashboard extracts."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_JS = ROOT / "dashboard" / "assets" / "dashboard-data.js"


def load_and_validate() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    suppliers = pd.read_csv(DATA / "suppliers_synthetic.csv")
    components = pd.read_csv(DATA / "components_synthetic.csv")
    orders = pd.read_csv(DATA / "purchase_orders_synthetic.csv", parse_dates=["order_date"])
    checks = {
        "duplicate_supplier_ids": int(suppliers["supplier_id"].duplicated().sum()),
        "duplicate_component_ids": int(components["component_id"].duplicated().sum()),
        "duplicate_purchase_orders": int(orders["purchase_order_id"].duplicated().sum()),
        "null_required_cells": int(
            suppliers.isna().sum().sum() + components.isna().sum().sum() + orders.isna().sum().sum()
        ),
        "orphan_suppliers": int((~orders["supplier_id"].isin(suppliers["supplier_id"])).sum()),
        "orphan_components": int((~orders["component_id"].isin(components["component_id"])).sum()),
        "nonpositive_quantity_or_cost": int(((orders["quantity"] <= 0) | (orders["unit_cost_eur"] <= 0)).sum()),
    }
    if any(checks.values()):
        raise ValueError(f"Data quality failed: {checks}")
    return suppliers, components, orders, checks


def main() -> dict:
    if not (DATA / "purchase_orders_synthetic.csv").exists():
        from generate_data import main as generate

        generate()
    suppliers, components, orders, checks = load_and_validate()
    fact = orders.merge(suppliers, on="supplier_id", validate="many_to_one").merge(
        components, on="component_id", validate="many_to_one"
    )
    if len(fact) != len(orders):
        raise AssertionError("Join changed purchase-order grain")
    fact["actual_spend_eur"] = fact["quantity"] * fact["unit_cost_eur"]
    fact["standard_spend_eur"] = fact["quantity"] * fact["standard_unit_cost_eur"]
    fact["ppv_eur"] = fact["actual_spend_eur"] - fact["standard_spend_eur"]
    fact["price_variance_pct"] = (fact["unit_cost_eur"] / fact["standard_unit_cost_eur"] - 1) * 100
    fact["defect_rate"] = fact["defective_quantity"] / fact["received_quantity"].clip(lower=1)
    fact["on_time"] = fact["delivery_delay_days"] <= 2
    fact["month"] = fact["order_date"].dt.to_period("M").astype(str)

    features = fact[["price_variance_pct", "delivery_delay_days", "defect_rate"]].copy()
    features["defect_rate"] *= 100
    median = features.median()
    mad = (features - median).abs().median().replace(0, 1)
    robust_z = 0.6745 * (features - median) / mad
    # Positive operational exceptions matter here; negative price variance and early delivery are not penalised.
    positive_z = robust_z.clip(lower=0)
    score = np.sqrt(
        0.38 * positive_z["price_variance_pct"] ** 2
        + 0.32 * positive_z["delivery_delay_days"] ** 2
        + 0.30 * positive_z["defect_rate"] ** 2
    )
    threshold = float(score.quantile(0.975))
    fact["anomaly_score"] = score.round(4)
    fact["is_anomaly"] = score >= threshold
    fact["anomaly_reason"] = np.select(
        [
            fact["defect_rate"] > fact["defect_rate"].quantile(0.97),
            fact["delivery_delay_days"] > fact["delivery_delay_days"].quantile(0.97),
            fact["price_variance_pct"] > fact["price_variance_pct"].quantile(0.97),
        ],
        ["High defect rate", "Late delivery", "High unit-price variance"],
        default="Multivariate exception",
    )

    supplier = (
        fact.groupby(["supplier_id", "supplier_name", "country", "contract_tier", "country_risk"])
        .agg(
            spend_eur=("actual_spend_eur", "sum"),
            orders=("purchase_order_id", "size"),
            on_time_rate=("on_time", "mean"),
            defect_rate=("defective_quantity", "sum"),
            received=("received_quantity", "sum"),
            price_volatility=("price_variance_pct", "std"),
            ppv_eur=("ppv_eur", "sum"),
            anomalies=("is_anomaly", "sum"),
        )
        .reset_index()
    )
    supplier["defect_rate"] = supplier["defect_rate"] / supplier["received"].clip(lower=1)

    def minmax(s: pd.Series) -> pd.Series:
        return (s - s.min()) / (s.max() - s.min() + 1e-9)

    supplier["risk_score"] = (
        35 * minmax(1 - supplier["on_time_rate"])
        + 35 * minmax(supplier["defect_rate"])
        + 20 * minmax(supplier["price_volatility"].fillna(0))
        + 10 * supplier["country_risk"] / 100
    ).round(1)
    supplier["risk_band"] = pd.cut(
        supplier["risk_score"], [-1, 45, 60, 101], labels=["Monitor", "Review", "Escalate"]
    ).astype(str)

    monthly = (
        fact.groupby("month")
        .agg(spend_eur=("actual_spend_eur", "sum"), standard_eur=("standard_spend_eur", "sum"), ppv_eur=("ppv_eur", "sum"), on_time_rate=("on_time", "mean"))
        .reset_index()
    )
    component = (
        fact.groupby(["component", "commodity_family", "commodity_exposure", "energy_exposure"])
        .agg(spend_eur=("actual_spend_eur", "sum"), ppv_eur=("ppv_eur", "sum"), defect_rate=("defective_quantity", "sum"), received=("received_quantity", "sum"))
        .reset_index()
    )
    component["defect_rate"] = component["defect_rate"] / component["received"].clip(lower=1)

    # Persist source tables and governed marts for SQL inspection.
    db = DATA / "procurement.db"
    with sqlite3.connect(db) as con:
        suppliers.to_sql("dim_supplier", con, if_exists="replace", index=False)
        components.to_sql("dim_component", con, if_exists="replace", index=False)
        orders.to_sql("fact_purchase_order", con, if_exists="replace", index=False)
        supplier.to_sql("mart_supplier_scorecard", con, if_exists="replace", index=False)
        monthly.to_sql("mart_monthly_cost", con, if_exists="replace", index=False)

    spend = fact["actual_spend_eur"].sum()
    summary = {
        "as_of": str(fact["order_date"].max().date()),
        "data_label": "Synthetic operational data",
        "annualized_spend_eur": round(float(spend / fact["order_date"].dt.to_period("M").nunique() * 12)),
        "ppv_eur": round(float(fact["ppv_eur"].sum())),
        "on_time_rate_pct": round(float(fact["on_time"].mean() * 100), 1),
        "defect_rate_pct": round(float(fact["defective_quantity"].sum() / fact["received_quantity"].sum() * 100), 2),
        "anomalies": int(fact["is_anomaly"].sum()),
        "suppliers_for_review": int((supplier["risk_band"] != "Monitor").sum()),
        "quality_checks_passed": len(checks),
    }

    exceptions = (
        fact.loc[fact["is_anomaly"]]
        .sort_values("anomaly_score", ascending=False)
        .loc[:, ["purchase_order_id", "order_date", "supplier_name", "component", "actual_spend_eur", "price_variance_pct", "delivery_delay_days", "defect_rate", "anomaly_reason"]]
        .head(35)
    )
    exceptions["order_date"] = exceptions["order_date"].dt.strftime("%Y-%m-%d")

    payload = {
        "summary": summary,
        "monthly": json.loads(monthly.round(4).to_json(orient="records")),
        "suppliers": json.loads(supplier.sort_values("risk_score", ascending=False).round(4).to_json(orient="records")),
        "components": json.loads(component.sort_values("spend_eur", ascending=False).round(4).to_json(orient="records")),
        "exceptions": json.loads(exceptions.round(4).to_json(orient="records")),
    }
    OUT_JS.write_text("window.DASHBOARD_DATA = " + json.dumps(payload, indent=2) + ";\n", encoding="utf-8")
    (DATA / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    fact.to_csv(DATA / "fact_enriched.csv", index=False)
    print(json.dumps(summary, indent=2))
    return payload


if __name__ == "__main__":
    main()
