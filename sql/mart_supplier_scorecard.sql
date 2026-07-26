-- Reference SQL model. The Python pipeline materializes the same governed grain.
with order_enriched as (
    select
        po.purchase_order_id,
        po.supplier_id,
        po.quantity * po.unit_cost_eur as actual_spend_eur,
        po.quantity * c.standard_unit_cost_eur as standard_spend_eur,
        case when po.delivery_delay_days <= 2 then 1.0 else 0.0 end as on_time,
        cast(po.defective_quantity as real) / nullif(po.received_quantity, 0) as defect_rate
    from fact_purchase_order po
    join dim_component c using (component_id)
)
select
    supplier_id,
    count(*) as purchase_orders,
    sum(actual_spend_eur) as spend_eur,
    sum(actual_spend_eur - standard_spend_eur) as ppv_eur,
    avg(on_time) as on_time_rate,
    avg(defect_rate) as average_order_defect_rate
from order_enriched
group by supplier_id;
