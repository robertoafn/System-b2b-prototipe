---
doc_id: "MVP-D02"
title: "V1.0 Core Data Contract"
version: "0.4"
status: "approved"
type: "data_specification"
created: "2026-08-13"
updated: "2026-08-16"
depends_on:
  - "MVP-D00"
  - "MVP-D01"
---

# V1.0 Core Data Contract

## 1. Propósito

Definir el contrato mínimo que deberán respetar:

```text
synthetic generator
→ validation
→ analytical marts
→ Power BI
```

Este documento es la autoridad para:

- granularidad;
- claves primarias;
- claves foráneas;
- campos mínimos;
- tipos lógicos;
- restricciones;
- semántica sintética.

No define todavía una base de datos productiva.

---

## 2. Invariantes

```text
1 row = 1 declared grain

PK != NULL
PK = UNIQUE

FK → valid parent

facts with different grain remain separate

synthetic operational data:
is_synthetic = true

semantic changes require contract update
```

La implementación no deberá modificar silenciosamente:

```text
grain
PK
FK
field meaning
temporal rules
synthetic-data semantics
```

### 2.1 Convenciones comunes

|Concepto|Contrato|
|---|---|
|Timezone|`America/Santiago`|
|Datetime|ISO 8601 con offset UTC explícito|
|Date|ISO 8601 `YYYY-MM-DD`|
|Moneda|CLP, neta de IVA|
|Redondeo monetario|2 decimales, half-up|
|Cantidad|decimal con hasta 3 decimales|
|Encoding CSV|UTF-8|
|Null|sólo permitido cuando se indique explícitamente|

Todos los datasets tabulares incluyen, además de sus campos específicos:

|Campo|Tipo lógico|Regla|
|---|---|---|
|`scenario_id`|string|`B2B-V1-BASE` para aceptación|
|`dataset_build_id`|string|determinista para configuración, seed y versiones|
|`is_synthetic`|boolean|`true`, salvo localización pública clasificada|

`dataset_build_id` no incorpora el timestamp de ejecución. Dos ejecuciones equivalentes deben producir archivos tabulares idénticos.

---

# 3. Datasets de V1.0 Core

```text
customers
products
locations
operational_sites
vehicles
orders
order_lines
inventory
deliveries
delivery_lines
cost_activities
```

Salida prevista:

```text
data/synthetic/<dataset>.csv
data/validated/<dataset>.parquet
data/manifest/run_manifest.json
```

CSV constituye la salida source sintética; Parquet es la salida validada preferida. El manifiesto no es un hecho de negocio y registra versiones, conteos, calidad y checksums.

Posteriormente estos datasets serán transformados en dimensiones y hechos para Power BI.

---

# 4. `customers`

**Grain**

```text
1 row = 1 customer
```

**PK**

```text
customer_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `customer_id` | string | PK |
| `customer_name` | string | required |
| `customer_segment` | string | required |
| `location_id` | string | FK → locations |
| `created_date` | date | required |
| `is_active` | boolean | required |
| `is_synthetic` | boolean | true |

ID:

```text
CUS-SYN-###
```

---

# 5. `products`

**Grain**

```text
1 row = 1 SKU
```

**PK**

```text
sku_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `sku_id` | string | PK |
| `sku_name` | string | required |
| `product_family` | string | required |
| `unit` | string | required |
| `reference_list_unit_price` | number | > 0 |
| `reference_variable_unit_cost` | number | >= 0 |
| `weight_kg` | number | > 0 |
| `volume_m3` | number | > 0 |
| `is_active` | boolean | required |
| `is_synthetic` | boolean | true |

Los precios y costos aquí son valores de referencia.

El valor transaccional utilizado para un pedido se conserva en `order_lines`.

---

# 6. `locations`

**Grain**

```text
1 row = 1 geographical location
```

**PK**

```text
location_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `location_id` | string | PK |
| `location_type` | string | `site` / `customer` |
| `commune` | string | required |
| `region` | string | required |
| `country_code` | string | `CL` |
| `latitude` | number | [-90, 90] |
| `longitude` | number | [-180, 180] |
| `data_class` | string | `synthetic` / `reference_location` |
| `is_synthetic` | boolean | consistent with `data_class` |

El nodo operacional:

```text
SOR-01
```

puede utilizar una localización geográfica de referencia con `data_class = reference_location` e `is_synthetic = false`.

Las ubicaciones de clientes del piloto serán sintéticas y deberán usar `data_class = synthetic` e `is_synthetic = true`.

---

# 6A. `operational_sites`

**Grain**

```text
1 row = 1 operational site
```

**PK**

```text
site_id
```

**FK**

```text
location_id → locations.location_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `site_id` | string | `SOR-01` en V1.0 |
| `location_id` | string | FK a location tipo `site` |
| `site_type` | string | `operational_logistics_node` |
| `is_active` | boolean | true en escenario base |
| `is_synthetic` | boolean | true |

La operación del sitio es hipotética aunque su ubicación pueda ser una referencia pública.

---

# 7. `vehicles`

**Grain**

```text
1 row = 1 vehicle
```

**PK**

```text
vehicle_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `vehicle_id` | string | PK |
| `vehicle_type` | string | required |
| `capacity_kg` | number | > 0 |
| `capacity_m3` | number | > 0 |
| `fixed_cost_day` | number | >= 0 |
| `variable_cost_km` | number | >= 0 |
| `is_active` | boolean | required |
| `is_synthetic` | boolean | true |

ID:

```text
VEH-SYN-##
```

---

# 8. `orders`

**Grain**

```text
1 row = 1 order
```

**PK**

```text
order_id
```

**FK**

```text
customer_id → customers.customer_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `order_id` | string | PK |
| `customer_id` | string | FK |
| `order_datetime` | datetime | required |
| `requested_delivery_datetime` | datetime | nullable; when present `>= order_datetime` |
| `promised_delivery_datetime` | datetime | `>= order_datetime` |
| `order_status` | string | controlled value |
| `is_synthetic` | boolean | true |

Estados V1.0 Core:

```text
confirmed
partially_fulfilled
fulfilled
```

Cancelaciones no se generan en `B2B-V1-BASE`. El estado se reconciliará con las cantidades acumuladas entregadas.

ID:

```text
ORD-SYN-######
```

---

# 9. `order_lines`

**Grain**

```text
1 row = 1 SKU within 1 order
```

**PK**

```text
order_line_id
```

**FK**

```text
order_id → orders.order_id
sku_id   → products.sku_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `order_line_id` | string | PK; `OLN-SYN-#######` |
| `order_id` | string | FK |
| `sku_id` | string | FK |
| `ordered_quantity` | number | > 0 |
| `list_unit_price` | number | > 0 |
| `synthetic_discount_per_unit` | number | [0, list_unit_price] |
| `net_unit_price` | number | derived; >= 0 |
| `unit_variable_cost` | number | >= 0 |
| `ordered_net_sales` | number | derived |
| `is_synthetic` | boolean | true |

Derivación:

```text
net_unit_price
=
list_unit_price - synthetic_discount_per_unit
```

```text
ordered_net_sales
=
ordered_quantity × net_unit_price
```

`ordered_net_sales` es informativo. Ventas reconocidas y costo variable realizado se calcularán sobre cantidad efectivamente entregada.

---

# 10. `inventory`

**Grain**

```text
1 row
=
1 SKU
× 1 operational site
× 1 snapshot date
```

**PK compuesta**

```text
snapshot_date
+ site_id
+ sku_id
```

**FK**

```text
site_id → operational_sites.site_id
sku_id  → products.sku_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `snapshot_date` | date | PK component |
| `site_id` | string | `SOR-01` |
| `sku_id` | string | PK/FK |
| `on_hand_quantity` | number | >= 0 |
| `allocated_quantity` | number | >= 0 |
| `available_quantity` | number | >= 0 |
| `safety_stock_quantity` | number | >= 0 |
| `reorder_point_quantity` | number | >= safety_stock_quantity |
| `is_stockout` | boolean | derived |
| `is_low_inventory` | boolean | derived |
| `is_synthetic` | boolean | true |

Reglas V1.0 Core:

```text
available_quantity
=
on_hand_quantity - allocated_quantity
```

```text
allocated_quantity <= on_hand_quantity
```

```text
is_stockout
=
available_quantity == 0
```

```text
is_low_inventory
=
0 < available_quantity <= reorder_point_quantity
```

El escenario base generará una observación diaria por cada combinación SOR-01 × SKU durante todo el período: 10.950 filas para 365 fechas × 30 SKU × 1 sitio.

Estas fórmulas son reglas del piloto, no políticas universales de inventario.

---

# 11. `deliveries`

**Grain**

```text
1 row = 1 delivery event for 1 order
```

Un pedido puede tener una o más entregas. Cada entrega pertenece a un solo pedido en V1.0 Core.

**PK**

```text
delivery_id
```

**FK**

```text
order_id                → orders.order_id
vehicle_id              → vehicles.vehicle_id
origin_site_id          → operational_sites.site_id
destination_location_id → locations.location_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `delivery_id` | string | PK; `DEL-SYN-######` |
| `order_id` | string | FK |
| `vehicle_id` | string | FK |
| `origin_site_id` | string | FK; `SOR-01` |
| `destination_location_id` | string | FK a ubicación del cliente del pedido |
| `delivery_sequence` | integer | > 0; unique dentro del pedido |
| `dispatch_datetime` | datetime | >= order_datetime |
| `delivery_datetime` | datetime | >= dispatch_datetime |
| `distance_km` | number | >= 0 |
| `delivery_status` | string | `delivered` / `delivered_with_incident` |
| `is_synthetic` | boolean | true |

# 11A. `delivery_lines`

**Grain**

```text
1 row = quantity of 1 order line included in 1 delivery
```

**PK**

```text
delivery_line_id
```

**FK**

```text
delivery_id   → deliveries.delivery_id
order_line_id → order_lines.order_line_id
```

| Campo | Tipo lógico | Regla |
|---|---|---|
| `delivery_line_id` | string | PK; `DLN-SYN-#######` |
| `delivery_id` | string | FK |
| `order_line_id` | string | FK |
| `delivered_quantity` | number | > 0 |
| `is_synthetic` | boolean | true |

La misma línea de pedido puede aparecer en varias entregas. Para cada fila, `deliveries.order_id` debe coincidir con `order_lines.order_id`.

```text
Σ delivered_quantity by order_line_id
<= ordered_quantity
```

No se permiten sobreentregas.

## Servicio derivable a nivel de pedido

```text
Order In Full
=
all order lines have cumulative delivered quantity >= ordered quantity
```

```text
completion_datetime
=
latest delivery_datetime required to complete all order lines
```

```text
Order On Time
=
Order In Full AND completion_datetime <= promised_delivery_datetime
```

```text
Order OTIF
=
Order In Full AND Order On Time
```

Para pedidos incompletos, la clasificación `partial_on_time` o `partial_late` seguirá `MVP-SPEC.md`. La fórmula KPI final permanece gobernada por `KPI-POWERBI-SPEC.md`.

---

# 12. `cost_activities`

**Grain**

```text
1 row
=
1 cost component
attributed to 1 order
```

**PK**

```text
cost_activity_id
```

**FK**

```text
order_id → orders.order_id
delivery_id → deliveries.delivery_id
```

`delivery_id` puede ser nulo cuando el costo corresponde al pedido completo.

| Campo | Tipo lógico | Regla |
|---|---|---|
| `cost_activity_id` | string | PK; `CST-SYN-########` |
| `order_id` | string | FK |
| `delivery_id` | string | nullable FK |
| `activity_datetime` | datetime | >= order_datetime |
| `cost_type` | string | controlled value |
| `cost_amount` | number | >= 0 |
| `currency_code` | string | `CLP` |
| `cost_driver_value` | number | nullable; when present >= 0 |
| `cost_driver_unit` | string | nullable; required when driver exists |
| `allocation_method` | string | controlled value |
| `is_synthetic` | boolean | true |

Tipos iniciales:

```text
order_processing
picking
handling
transport
delivery
incident
```

Métodos de asignación iniciales:

```text
direct_order
direct_delivery
proportional_weight
proportional_volume
proportional_distance
```

`transport` y `delivery` requieren `delivery_id`. Cada actividad se registra una sola vez; sumar CTS no debe duplicar costos por joins con líneas.

La separación de costos por actividad permite evolucionar posteriormente hacia TDABC sin exigirlo en V1.0 Core.

---

# 13. Métricas económicas derivables

## Net Sales

```text
Net Sales
=
Σ(
  delivery_lines.delivered_quantity
  × order_lines.net_unit_price
)
```

## Variable Product Cost

```text
Variable Product Cost
=
Σ(
  delivery_lines.delivered_quantity
  × order_lines.unit_variable_cost
)
```

Las cantidades no entregadas no reconocen ventas ni costo variable. `ordered_net_sales` no forma parte de Net Sales oficial.

## Contribution Margin

```text
Contribution Margin
=
Net Sales
-
Variable Product Cost
```

## Cost-to-Serve

```text
CTS
=
Σ cost_amount
```

## MC_CTS

```text
MC_CTS
=
Contribution Margin
-
CTS
```

`MC_CTS` no debe denominarse margen neto.

El CTS se modela por actividades porque el costo de atender clientes puede modificar materialmente la rentabilidad observada a partir del margen de producto.

---

# 14. Relaciones mínimas

```text
Customer 1 ── N Order

Location 1 ── N Customer

Location 1 ── N OperationalSite

OperationalSite 1 ── N InventorySnapshot

OperationalSite 1 ── N Delivery

Order 1 ── N OrderLine

Order 1 ── 0..N Delivery

Product 1 ── N OrderLine

Product 1 ── N InventorySnapshot

Delivery 1 ── N DeliveryLine

OrderLine 1 ── 0..N DeliveryLine

Vehicle 1 ── N Delivery

Location 1 ── N Delivery

Order 1 ── N CostActivity

Delivery 1 ── 0..N CostActivity
```

---

# 15. Quality Gates

La implementación deberá validar como mínimo:

## Schema

```text
required columns exist
logical types are valid
```

## PK

```text
PK has no NULL
PK is UNIQUE
```

## FK

```text
orphan FK count = 0
```

## Quantities

```text
ordered_quantity > 0

delivered_quantity > 0

sum(delivered_quantity by order_line_id) <= ordered_quantity

inventory quantities >= 0

allocated_quantity <= on_hand_quantity

available_quantity = on_hand_quantity - allocated_quantity
```

## Economics

```text
list_unit_price > 0
0 <= synthetic_discount_per_unit <= list_unit_price
net_unit_price = list_unit_price - synthetic_discount_per_unit
unit_variable_cost >= 0
cost_amount >= 0
```

## Time

```text
order_datetime <= requested_delivery_datetime, when present

order_datetime <= promised_delivery_datetime

order_datetime <= dispatch_datetime

dispatch_datetime <= delivery_datetime
```

## Cross-dataset business rules

```text
delivery.order_id = order_line.order_id for every delivery_line
delivery.destination_location_id = customer.location_id for the delivery order
cost_activity.order_id = delivery.order_id when delivery_id is present
transport/delivery cost activities require delivery_id
order_status reconciles with cumulative delivered quantities
daily inventory coverage exists for every site × SKU × date
order_datetime >= customer.created_date
UNIQUE(order_id, sku_id) in order_lines
UNIQUE(order_id, delivery_sequence) in deliveries
UNIQUE(delivery_id, order_line_id) in delivery_lines
delivery weight and volume do not exceed vehicle capacity
```

## Geography

```text
-90 <= latitude <= 90

-180 <= longitude <= 180
```

## Synthetic provenance

Para datos operacionales generados:

```text
is_synthetic = true
```

La única excepción permitida es una fila de `locations` clasificada como `reference_location`.

---

# 16. Reproducibilidad

El generador deberá registrar como mínimo:

```yaml
scenario_id: "B2B-V1-BASE"
data_class: "synthetic"
seed: 20260813
generator_version: "0.1.0"
schema_version: "1.0.0-rc.1"
config_sha256: "required"
dataset_build_id: "required"
```

Misma configuración + mismas versiones + misma semilla debe producir los mismos IDs, filas, valores ordenados y checksums tabulares.

El manifiesto registrará además:

```text
execution_id
executed_at
input and output paths
rows read, written and rejected by dataset
rejection reasons
artifact SHA-256
quality-gate results
execution duration and status
sanitized error, if any
```

La implementación deberá generar deliberadamente variabilidad suficiente para representar:

```text
stockouts
on-time / late deliveries
full / partial deliveries
heterogeneous CTS
different customer profitability
territorial variation
```

Gates mínimos para `B2B-V1-BASE`:

```text
customers = 150
products = 30
vehicles = 6
operational_sites = 1
orders within 4000 ± 5%
order_lines within 10000 ± 10%
complete_on_time_orders >= 60% of eligible orders
each remaining service class >= 5% of eligible orders
stockout observations >= 1%
low-inventory observations >= 5%
customers in each sales/CTS quadrant >= 5
```

sin presentar dichas relaciones sintéticas como evidencia empresarial real.

---

# 17. Salida analítica

Este contrato gobierna los datasets sintéticos.

La transformación posterior deberá producir el modelo establecido en `KPI-POWERBI-SPEC.md`:

```text
DIMENSIONS

dim_customer
dim_product
dim_location
dim_operational_site
dim_vehicle
dim_date
```

```text
FACTS

fact_orders
fact_order_lines
fact_deliveries
fact_delivery_lines
fact_inventory
fact_cost_to_serve
```

No crear una mega-tabla que combine hechos de granularidades diferentes.

`KPI-POWERBI-SPEC.md` deberá conservar estos grains o documentar explícitamente una proyección equivalente que no pierda entregas divididas ni amplifique joins.

---

# 18. Acceptance Gate

El contrato estará implementado cuando tests deterministas demuestren:

```text
[ ] schemas válidos
[ ] PK no nulas
[ ] PK únicas
[ ] FK sin huérfanos
[ ] rangos válidos
[ ] fechas consistentes
[ ] generación reproducible
[ ] is_synthetic preservado
[ ] pedido reconstruible end-to-end
[ ] múltiples entregas y líneas parciales reconciliables
[ ] cero sobreentregas acumuladas
[ ] Fill Rate reproducible
[ ] OTIF reproducible a grain Order
[ ] CTS reconciliable
[ ] MC_CTS reconciliable
[ ] marts conservan el grain definido
[ ] escenarios mínimos de B2B-V1-BASE presentes
[ ] manifiesto y checksums emitidos
[ ] fixtures inválidos son rechazados por el gate correspondiente
```

La validación debe poder expresarse posteriormente mediante:

```text
Python
+ pandas
+ pytest
```

antes de introducir frameworks adicionales.

---

# 19. Regla para agentes y Codex

Cuando:

```text
implementation != DATA-CONTRACT.md
```

el agente debe:

```text
1. reportar la divergencia
2. identificar archivos/tests afectados
3. preservar el contrato vigente
4. no realizar migración semántica silenciosa
```

Un cambio de:

```text
grain
PK
FK
campo
semántica
restricción
```

requiere modificar explícitamente este documento.

---

# 20. Estado

```yaml
PROJECT_PROGRESS:
  target_release: "V1.0"
  release_status: "V1.0"
  stage: "RELEASED"
  current_work_item: "V1.0-RELEASE"
  status: "COMPLETE"
  completed:
    - "MVP-D00"
    - "MVP-D01"
    - "MVP-D02"
    - "MVP-D03"
    - "MVP-D04"
    - "MVP-I01"
    - "MVP-I02"
    - "MVP-I03"
    - "MVP-I04"
    - "PBI-00"
    - "PBI-01"
    - "PBI-02"
    - "PBI-03"
    - "PBI-04"
    - "PBI-05"
  next: "POST_V1_BACKLOG_REQUIRES_NEW_CONTRACT"
  blockers: []
```

---

# 21. Registro de cambios

|Fecha|Versión documento|Estado|Cambio|
|---|---|---|---|
|2026-08-13|0.1|draft|Contrato ampliado por el usuario desde el borrador incompleto.|
|2026-08-13|0.2|approved|Se reconcilia y aprueba contra D00/D01: sitios, entregas múltiples, líneas de entrega, reconocimiento por cantidad entregada, manifiesto, calidad y reproducibilidad V1.0.|
|2026-08-16|0.3|approved|Se sincroniza el estado RELEASE_CANDIDATE sin alterar grains, claves, campos, restricciones ni semántica económica.|
|2026-08-16|0.4|approved|Se promueve el contrato implementado a V1.0 por aceptación explícita del usuario, sin cambios semánticos adicionales.|
