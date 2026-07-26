# Data governance note

## Ownership and grain

- `dim_supplier`: one current master-data row per synthetic supplier.
- `dim_component`: one row per component family and standard cost.
- `fact_purchase_order`: one row per purchase order.
- `mart_supplier_scorecard`: one row per supplier for the full selected period.
- `mart_monthly_cost`: one row per calendar month.

## Quality controls

The pipeline stops on duplicate primary keys, required-field nulls, orphan supplier/component keys, non-positive quantities or costs, and any join that changes the purchase-order grain.

## Metadata that a production implementation would add

- source-system owner and extraction timestamp
- effective-dated supplier and contract attributes
- currency and unit-of-measure conversion lineage
- part-revision and plant scope
- deletion/retention policy
- access classification and supplier-confidentiality controls
- SLA for late-arriving invoices and quality records

## Synthetic-data boundary

Supplier names and operational records are synthetic. Public commodity and policy sources frame the problem but are not represented as observed supplier performance.
