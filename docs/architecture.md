# Architecture and analytical contracts

The default repository is deliberately local and reviewable: CSV source tables, a deterministic Python transformation layer, a SQLite warehouse and a static management UI.

For an enterprise deployment:

1. Land ERP, quality and supplier master extracts in object storage.
2. Run schema and freshness checks before transformation.
3. Use Spark/Glue or a governed warehouse transformation service for incremental models.
4. Publish documented gold marts to Power BI/Tableau/SAP Analytics Cloud.
5. Monitor risk-model drift and require named business owners for score thresholds.

The anomaly model is a review queue, not an accusation. Every exception retains the source purchase-order identifier and reason field.
