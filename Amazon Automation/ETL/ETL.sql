/*+ ETLM
   {
       depend:
       {
        add:
           [                             
              	{ name:"axxes.aftbi_ddl.o_pending_customer_shipments"}, 
                 {name:"axxes.eu_xxef_analytics.veritas_ef", cutoff:{hours:1}}
          ]
       }
    }
*/

UNLOAD ($$
with whs as (SELECT warehouse,
                    CASE
                        WHEN nodetype = 'vendorFlex' THEN 'VendorFlex'
                        WHEN nodetype = 'popUp' THEN 'PopUp'
                        WHEN nodetype = 'thirdPartyLogistics' Then 'Amazon3PL' END as warehouse_type,
                    CASE WHEN country_code  in ('DE' , 'PL', 'CZ')              then 'DE'
                                WHEN country_code in ('UK') THEN 'GB'
                                ELSE  country_code                                       END        as country_code,
                    weeklymaxoutboundmechcapacity
             FROM andes.eu_efxx_analytics.veritas_ef
             WHERE isdeleted = 0
               AND status <> 'Closed'
               AND warehouse_type = 'Amazon3PL'
               AND country_code <> 'TR'
               AND warehouse not in ('xxx', 'xx', 'Xxx', 'XUxx', 'xxTF', 'Xxx', 'Xxx')
),

max_date as (

select snapshot_day, max(last_updated) as max_update from andes.aftbi_ddl.o_pending_customer_shipments b 
    INNER JOIN whs whs ON whs.warehouse = b.warehouse_id
    where b.region_id = 2 and snapshot_day='{RUN_DATE_YYYY-MM-DD}'
group by 1
)




   SELECT pcs.warehouse_id                    AS warehouse_id,
                  whs.warehouse_type,
                  whs.country_code,
                  TO_CHAR(pcs.snapshot_day, 'YYYY-MM-DD') as snapshot_date,
                  shipment_id,
                  amzn_id_mask.encrypt_shipment_id(pcs.shipment_id) as encrypt_shipment_id,
                  order_id,
                  condition,
                  ship_method,
                  expected_ship_date,
                  sort_code,
                  last_updated,
                  case when ROUND(datediff(days,last_updated,pcs.snapshot_day))<0 then 0 else ROUND(datediff(days,last_updated,pcs.snapshot_day)) end   AS days_since_last_update,
                  pcs.total_quantity                languishing_units
         FROM andes.aftbi_ddl.o_pending_customer_shipments AS pcs
                  INNER JOIN whs whs ON whs.warehouse = pcs.warehouse_id
                  left join max_date on pcs.snapshot_day=max_date.snapshot_day
                  
		--	where snapshot_day=current_date-1
        -- WHERE snapshot_day='{RUN_DATE_YYYY-MM-DD}'
        	WHERE pcs.snapshot_day='{RUN_DATE_YYYY-MM-DD}'
            --(select max(snapshot_day) from andes.aftbi_ddl.o_pending_customer_shipments a where a.region_id = 2)
            
            -- new condition to exclude not stuck shipments. TT: https://issues.amazon.com/EU-EF-OE-5982
          --  and datediff(min, last_updated, (select max(last_updated) from andes.aftbi_ddl.o_pending_customer_shipments b where b.region_id = 2 and snapshot_day='{RUN_DATE_YYYY-MM-DD}' ))>60
            
            and datediff(min, last_updated, max_update)>60
            

           AND pcs.region_id = 2
           and condition in (60,6001,6003,6006,6009)
           AND (fulfillment_brand_code not IN ('RMVL_OVERSTOCK', 'RMVL_DAMAGE') OR fulfillment_brand_code IS NULL) order by 1
$$)
TO 's3://etl-jobs-ctxx/stuckshipment/ETL/stuck'
    credentials 'aws_iam_role=arn:aws:iam::xxxxxxx:role/RedshiftS3Access,arn:aws:iam::xxxxxx:role/ef-oe-prod1-s3-access-role'
    region 'us-east-1'    
    CSV
    header
    NULL as '\\N'
    allowoverwrite
    EXTENSION 'csv'
    parallel off
    MAXFILESIZE 999MB;           
