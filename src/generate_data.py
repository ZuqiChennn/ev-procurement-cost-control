"""Generate a reproducible synthetic EV-battery procurement dataset."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

COMPONENTS = [
    ("Cathode active material", "Lithium/Nickel", 31.0, 0.58, 0.16),
    ("Anode graphite", "Graphite", 9.4, 0.47, 0.13),
    ("Cell casing", "Aluminium", 4.8, 0.22, 0.20),
    ("Copper busbar", "Copper", 7.2, 0.40, 0.11),
    ("Battery cell", "Multi-material", 74.0, 0.52, 0.18),
    ("Battery management system", "Electronics", 118.0, 0.08, 0.09),
    ("Thermal management plate", "Aluminium", 28.0, 0.16, 0.24),
    ("Module housing", "Aluminium", 42.0, 0.18, 0.26),
    ("High-voltage connector", "Copper/Electronics", 18.0, 0.18, 0.10),
    ("Pack seal & insulation", "Polymers", 13.0, 0.06, 0.14),
]


def main(seed: int = 73, suppliers_n: int = 54, orders_n: int = 4_800) -> None:
    rng = np.random.default_rng(seed)
    DATA.mkdir(parents=True, exist_ok=True)

    countries = np.array(["DE", "PL", "CZ", "HU", "SE", "FI", "PT", "CN", "KR"])
    country_p = np.array([0.20, 0.13, 0.12, 0.08, 0.07, 0.06, 0.06, 0.16, 0.12])
    country_risk = {"DE": 12, "PL": 19, "CZ": 17, "HU": 24, "SE": 10, "FI": 9, "PT": 15, "CN": 42, "KR": 21}
    supplier_country = rng.choice(countries, suppliers_n, p=country_p)
    suppliers = pd.DataFrame(
        {
            "supplier_id": [f"SUP-{i:03d}" for i in range(suppliers_n)],
            "supplier_name": [f"Supplier {chr(65 + i // 26)}{i % 26 + 1:02d}" for i in range(suppliers_n)],
            "country": supplier_country,
            "country_risk": [country_risk[x] for x in supplier_country],
            "contract_tier": rng.choice(["Strategic", "Preferred", "Approved"], suppliers_n, p=[0.24, 0.46, 0.30]),
        }
    )

    components = pd.DataFrame(
        COMPONENTS,
        columns=["component", "commodity_family", "standard_unit_cost_eur", "commodity_exposure", "energy_exposure"],
    )
    components.insert(0, "component_id", [f"CMP-{i:03d}" for i in range(len(components))])

    dates = pd.date_range("2024-01-01", "2026-06-30", freq="D")
    lithium_index = pd.Series(np.linspace(112, 89, len(dates)) + 7 * np.sin(np.linspace(0, 10, len(dates))), index=dates)
    metals_index = pd.Series(np.linspace(94, 108, len(dates)) + 4 * np.sin(np.linspace(0, 16, len(dates))), index=dates)
    energy_index = pd.Series(np.linspace(118, 102, len(dates)) + 6 * np.sin(np.linspace(0, 12, len(dates))), index=dates)

    order_date = pd.to_datetime(rng.choice(dates, orders_n))
    comp_idx = rng.choice(len(components), orders_n, p=np.array([.15,.09,.07,.08,.22,.10,.08,.08,.06,.07]))
    supplier_idx = rng.integers(0, suppliers_n, orders_n)
    comp = components.iloc[comp_idx].reset_index(drop=True)
    supp = suppliers.iloc[supplier_idx].reset_index(drop=True)
    quantity = rng.integers(180, 6_000, orders_n)

    commodity_factor = np.array([
        lithium_index[d] if "Lithium" in fam or fam == "Multi-material" else metals_index[d]
        for d, fam in zip(order_date, comp["commodity_family"])
    ]) / 100
    energy_factor = np.array([energy_index[d] for d in order_date]) / 100
    quality_effect = np.where(supp["contract_tier"].to_numpy() == "Strategic", -0.01, np.where(supp["contract_tier"].to_numpy() == "Approved", 0.02, 0))
    negotiated = rng.normal(0, 0.035, orders_n) + quality_effect
    unit_cost = comp["standard_unit_cost_eur"].to_numpy() * (
        1
        + comp["commodity_exposure"].to_numpy() * (commodity_factor - 1)
        + comp["energy_exposure"].to_numpy() * (energy_factor - 1)
        + negotiated
    )

    supplier_delay_base = rng.gamma(1.1, 1.2, suppliers_n)
    supplier_defect_base = rng.uniform(0.002, 0.022, suppliers_n)
    delay = np.round(rng.normal(supplier_delay_base[supplier_idx], 2.2)).astype(int)
    delay = np.clip(delay, -4, 45)
    defect_rate = np.clip(rng.lognormal(np.log(supplier_defect_base[supplier_idx] + 0.001), 0.52), 0, 0.15)

    # Plant a small number of review-worthy operational events.
    shock = rng.choice(orders_n, 75, replace=False)
    unit_cost[shock[:35]] *= rng.uniform(1.14, 1.30, 35)
    delay[shock[35:55]] += rng.integers(12, 28, 20)
    defect_rate[shock[55:]] *= rng.uniform(2.8, 5.0, 20)

    received_qty = quantity
    defective_qty = np.minimum(received_qty, np.round(received_qty * defect_rate)).astype(int)
    orders = pd.DataFrame(
        {
            "purchase_order_id": [f"PO-{i:06d}" for i in range(orders_n)],
            "order_date": order_date.strftime("%Y-%m-%d"),
            "supplier_id": supp["supplier_id"],
            "component_id": comp["component_id"],
            "quantity": quantity,
            "received_quantity": received_qty,
            "defective_quantity": defective_qty,
            "unit_cost_eur": np.round(unit_cost, 2),
            "delivery_delay_days": delay,
            "lithium_index": [round(lithium_index[d], 2) for d in order_date],
            "metals_index": [round(metals_index[d], 2) for d in order_date],
            "industrial_energy_index": [round(energy_index[d], 2) for d in order_date],
        }
    ).sort_values("order_date")

    suppliers.to_csv(DATA / "suppliers_synthetic.csv", index=False)
    components.to_csv(DATA / "components_synthetic.csv", index=False)
    orders.to_csv(DATA / "purchase_orders_synthetic.csv", index=False)
    print(f"Wrote {len(suppliers)} suppliers, {len(components)} components and {len(orders):,} orders.")


if __name__ == "__main__":
    main()
