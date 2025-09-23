# ETL: Stuck Shipments en Amazon 3PL EU

## 📌 Descripción
Esta ETL en Redshift identifica **envíos atascados (stuck shipments)** en warehouses **3PL de Europa** y exporta los resultados a un bucket de **Amazon S3** en formato CSV.  
El objetivo es generar un dataset actualizado diariamente para monitorizar envíos que no han tenido actualización en más de 60 minutos y se encuentran en condiciones específicas.

---

## 🔄 Flujo del proceso

### 1. **Dependencias**
Antes de ejecutar, la ETL asegura la disponibilidad de las siguientes tablas:
- `andes.aftbi_ddl.o_pending_customer_shipments`
- `andes.eu_ef_analytics.veritas_ef` (con cutoff de 1 hora)

---

### 2. **Inputs principales**
- **Tabla 1: `andes.aftbi_ddl.o_pending_customer_shipments`**  
  Contiene envíos pendientes, con información de:
  - `shipment_id`, `order_id`
  - `condition`, `ship_method`
  - `expected_ship_date`, `last_updated`
  - `total_quantity`

- **Tabla 2: `andes.eu_ef_analytics.veritas_ef`**  
  Contiene metadatos de warehouses:
  - `warehouse`, `nodetype`, `country_code`
  - `weeklymaxoutboundmechcapacity`
  - `status`, `isdeleted`

---

### 3. **Transformaciones (CTEs)**
- **`whs`**  
  - Filtra warehouses de tipo **Amazon3PL** activos.  
  - Normaliza países (`DE` agrupa DE/PL/CZ, `GB` para UK).  
  - Excluye Turquía y algunos sites específicos.  

- **`max_date`**  
  - Calcula el `max(last_updated)` para cada `snapshot_day` en `o_pending_customer_shipments`.  
  - Sirve como referencia de última actualización para determinar si un envío está atascado.  

---

### 4. **Selección final**
Se seleccionan los envíos pendientes con:
- `pcs.snapshot_day = {RUN_DATE_YYYY-MM-DD}`
- `datediff(min, last_updated, max_update) > 60`  
  (no actualizados en la última hora → stuck)
- `pcs.region_id = 2` (Europa)
- `condition in (60,6001,6003,6006,6009)`  
- Excluye removals (`fulfillment_brand_code NOT IN ('RMVL_OVERSTOCK','RMVL_DAMAGE')`)

Campos generados:
- `warehouse_id`, `warehouse_type`, `country_code`
- `shipment_id` (más versión encriptada)
- `order_id`, `condition`, `ship_method`
- `expected_ship_date`, `sort_code`
- `days_since_last_update`
- `total_quantity` → `languishing_units`

---

### 5. **Output**
El resultado se exporta a S3:

