from pathlib import Path
import sqlite3
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline import load_and_validate, main


class PipelineTests(unittest.TestCase):
    def test_source_contract_and_join_grain(self):
        suppliers, components, orders, checks = load_and_validate()
        self.assertFalse(any(checks.values()))
        joined = orders.merge(suppliers, on="supplier_id", validate="many_to_one").merge(
            components, on="component_id", validate="many_to_one"
        )
        self.assertEqual(len(joined), len(orders))

    def test_dashboard_metrics_are_plausible(self):
        payload = main()
        s = payload["summary"]
        self.assertGreater(s["annualized_spend_eur"], 0)
        self.assertTrue(0 < s["on_time_rate_pct"] <= 100)
        self.assertTrue(0 <= s["defect_rate_pct"] < 10)
        self.assertGreater(s["anomalies"], 0)
        self.assertTrue(all(0 <= x["risk_score"] <= 100 for x in payload["suppliers"]))

    def test_sql_marts_exist_and_reconcile(self):
        with sqlite3.connect(ROOT / "data" / "procurement.db") as con:
            source_n = con.execute("select count(*) from fact_purchase_order").fetchone()[0]
            suppliers_n = con.execute("select count(*) from mart_supplier_scorecard").fetchone()[0]
        self.assertEqual(source_n, len(pd.read_csv(ROOT / "data" / "purchase_orders_synthetic.csv")))
        self.assertEqual(suppliers_n, len(pd.read_csv(ROOT / "data" / "suppliers_synthetic.csv")))


if __name__ == "__main__":
    unittest.main()
