---
doc_id: "MVP-D01"
title: "V1.0 Core Specification"
version: "0.4"
status: "approved"
type: "specification"
created: "2026-08-13"
updated: "2026-08-16"
depends_on:
  - "MVP-D00"
---

# V1.0 Core Specification

## 1. Objetivo

Construir la primera versión funcional local de un **Sistema Comercial–Operacional B2B** utilizando datos exclusivamente sintéticos/hipotéticos y Power BI como capa final de análisis.

V1.0 Core debe demostrar que es posible conectar:

```text
Customer
→ Order
→ SKU
→ Inventory
→ Delivery
→ Service
→ Cost-to-Serve
→ MC_CTS
→ Decision
```

El objetivo no es reproducir un ERP completo, sino demostrar un flujo mínimo, trazable, reproducible y ampliable.

Este documento define el comportamiento observable de V1.0 Core. `DATA-CONTRACT.md` definirá después tablas, campos, tipos, claves y granularidades físicas.

---

## 2. Sitio operacional

```yaml
site_id: "SOR-01"
location_reference: "Las Esteras Sur, Quilicura, Región Metropolitana, Chile"
type: "operational_logistics_node"
timezone: "America/Santiago"
currency: "CLP"
data_class: "reference_location"
```

SOR-01 representa hipotéticamente:

- almacenamiento;

- inventario;

- picking;

- preparación;

- consolidación;

- despacho;

- distribución B2B.

Las coordenadas operacionales utilizadas por el dataset serán sintéticas o de referencia pública y deberán clasificarse explícitamente. La dirección de referencia no autoriza el uso de datos corporativos reales.


---

## 3. Escenario sintético

Configuración base de aceptación:

```yaml
scenario_id: "B2B-V1-BASE"
seed: 20260813
period_start: "2025-08-01"
period_end: "2026-07-31"
timezone: "America/Santiago"
currency: "CLP"
customers_exact: 150
skus_exact: 30
vehicles_exact: 6
operational_sites_exact: 1
orders_target: 4000
orders_tolerance_pct: 5
order_lines_target: 10000
order_lines_tolerance_pct: 10
```

Otra configuración podrá utilizarse para desarrollo, pero la aceptación V1.0 se ejecutará con `B2B-V1-BASE`.

Los datos deberán contener variabilidad suficiente para producir:

- clientes frecuentes y esporádicos;

- pedidos grandes y pequeños;

- diferentes combinaciones de SKU;

- distintos márgenes;

- stockouts;

- entregas tardías;

- entregas parciales;

- distintos costos logísticos;

- diferentes zonas geográficas;

- clientes con CTS alto y bajo.

Cobertura mínima del escenario base:

```text
complete_on_time_orders >= 60% de pedidos elegibles
complete_late_orders >= 5% de pedidos elegibles
partial_on_time_orders >= 5% de pedidos elegibles
partial_late_orders >= 5% de pedidos elegibles
stockout_observations >= 1% de observaciones de inventario
low_inventory_observations >= 5% de observaciones de inventario
customers_in_each_sales_cts_quadrant >= 5
```

Las categorías pueden solaparse cuando corresponda. Los porcentajes son gates de cobertura sintética, no afirmaciones sobre una operación real.


---

## 4. Entidades mínimas

V1.0 Core requiere como mínimo:

```text
Operational Site
Customer
Product / SKU
Order
Order Line
Inventory
Delivery
Delivery Line
Vehicle
Location
Cost Activity
```

Relaciones conceptuales:

```text
Customer
  └── Order
        └── Order Line
              └── SKU

Operational Site
  └── Inventory
        └── SKU

Order
  └── Delivery [1..N]
        ├── Delivery Line
        │     └── Order Line
        ├── Vehicle
        └── Location

Delivery
  └── Cost Activity
```

Reglas funcionales de cardinalidad para V1.0:

- un pedido pertenece a un solo cliente;
- un pedido contiene una o más líneas;
- una línea corresponde a un solo SKU;
- un pedido puede resolverse mediante una o más entregas;
- una entrega pertenece a un solo pedido en V1.0 Core;
- una entrega contiene una o más líneas de entrega;
- una línea de entrega aplica cantidad a una línea del mismo pedido;
- un vehículo puede realizar muchas entregas;
- una actividad CTS se registra una sola vez y debe poder atribuirse al pedido o entrega que la originó.

`Service` no será una entidad independiente en V1.0. Será el resultado derivado de fechas prometidas/reales y cantidades pedidas/entregadas.

La definición física de tablas y claves se realizará en `DATA-CONTRACT.md`.

---

## 5. Flujo operacional mínimo

```text
1. Cliente genera pedido
2. Pedido recibe fecha/hora prometida y contiene una o más líneas SKU
3. Se consulta disponibilidad por sitio y SKU
4. Se asigna inventario disponible
5. Se prepara despacho total o parcial
6. Se asigna vehículo
7. Se ejecuta una o más entregas por pedido
8. Se registran cantidades entregadas por línea y fecha/hora real
9. Se deriva el resultado de servicio
10. Se registran actividades de Cost-to-Serve
11. Se calcula MC_CTS sobre cantidades económicamente reconocidas
12. Power BI consume las tablas analíticas
```

No es necesario implementar sistemas transaccionales reales en esta etapa.

El flujo debe preservar la secuencia temporal mínima:

```text
order_datetime
<= promised_delivery_datetime

order_datetime
<= dispatch_datetime
<= actual_delivery_datetime
```

Cuando existan múltiples entregas, cada evento conservará su propia fecha/hora y cantidad. El cierre del pedido se evaluará con la entrega acumulada de todas sus líneas.

---

## 6. Casos que el dataset debe permitir observar

### Servicio

La unidad de evaluación de OTIF será el pedido elegible. Un pedido es elegible cuando no está cancelado, su fecha prometida está dentro del período del escenario y existe información suficiente para evaluar su resultado al cierre del dataset.

Definiciones funcionales:

```text
in_full = cada línea tiene cumulative_delivered_quantity >= ordered_quantity
on_time = in_full y completion_datetime <= promised_delivery_datetime
otif = in_full y on_time
```

Clasificación final y mutuamente excluyente:

- `complete_on_time`: todas las líneas completas antes o en la fecha/hora prometida;
- `complete_late`: todas las líneas completas después de la fecha/hora prometida;
- `partial_on_time`: pedido incompleto al cierre, pero con cantidad positiva entregada antes o en la fecha/hora prometida;
- `partial_late`: pedido incompleto al cierre y sin cantidad positiva entregada dentro de la promesa.

No se permitirán sobreentregas en V1.0 Core. El tratamiento de cancelaciones, devoluciones y notas de crédito queda fuera del escenario base.

### Inventario

El escenario base generará una observación diaria de cierre por sitio y SKU.

```text
available_quantity = on_hand_quantity - allocated_quantity

stockout: available_quantity = 0
low_inventory: 0 < available_quantity <= reorder_point_quantity
normal_inventory: available_quantity > reorder_point_quantity
allocated_inventory: allocated_quantity > 0
```

`allocated_inventory` es un indicador que puede coexistir con cualquiera de los otros estados.

### Cliente

Los cuadrantes de cliente se calcularán para todo el período base usando las medianas de ventas reconocidas y CTS como cortes sintéticos:

```text
high sales + low CTS
high sales + high CTS
low sales + low CTS
low sales + high CTS
```

Cada cuadrante deberá contener al menos cinco clientes. Esta clasificación busca demostrar que volumen de ventas y rentabilidad no son equivalentes; no representa una segmentación corporativa real.

## 7. Cost-to-Serve mínimo

El CTS inicial será sintético y explicable.

Componentes mínimos:

```text
order_processing_cost
picking_cost
handling_cost
transport_cost
delivery_cost
return_or_incident_cost
```

Forma conceptual:

```text
CTS
=
Order Processing
+ Picking
+ Handling
+ Transport
+ Delivery
+ Incidents
```

No es obligatorio implementar todavía un modelo TDABC completo.

TDABC queda como método de evolución posterior del CTS.

Reglas mínimas:

- todos los importes estarán expresados en CLP, sin IVA;
- `transport_cost` representa desplazamiento del vehículo atribuible por distancia/tiempo;
- `delivery_cost` representa la parada y el servicio físico en el cliente;
- `return_or_incident_cost` se utilizará en V1.0 sólo para incidentes sintéticos; las devoluciones operacionales quedan fuera del Core;
- cada actividad de costo tendrá una identidad única y se sumará una sola vez;
- todo costo compartido deberá declarar su método de asignación;
- CTS deberá reconciliar desde actividad hacia entrega, pedido, cliente y período;
- no se permitirán costos negativos en el escenario base.

---

## 8. Función económica

Métrica principal:

```text
MC_CTS
=
Net Sales
-
Variable Product Cost
-
Cost-to-Serve
```

No denominar `MC_CTS` como margen neto.

Reconocimiento económico V1.0:

```text
Net Unit Price
=
List Unit Price
- Synthetic Discount

Recognized Net Sales
=
Delivered Quantity
× Net Unit Price

Variable Product Cost
=
Delivered Quantity
× Unit Variable Cost

Contribution Margin
=
Recognized Net Sales
- Variable Product Cost

MC_CTS
=
Contribution Margin
- Cost-to-Serve
```

Los precios serán netos de IVA. Las cantidades no entregadas no reconocerán ventas ni costo variable. Cancelaciones, devoluciones, impuestos, notas de crédito y costos financieros quedan fuera del Core.

Debe poder calcularse al menos por:

```text
Customer
Order
Period
```

Los totales deberán reconciliar entre el nivel de pedido, cliente y período sin duplicación por joins.

---

## 9. KPIs mínimos de V1.0

V1.0 debe poder obtener:

```text
Net Sales
Contribution Margin
CTS
MC_CTS
Orders
Average Order Value
OTIF
Fill Rate
Lead Time
Stockout Rate
Inventory
Customer Frequency
Delivery Distance
Transport Cost
Vehicle Utilization
Customers
```

`KPI-POWERBI-SPEC.md` deberá definir para cada KPI:

```text
business question
formula
numerator
denominator
grain
date role
eligible population
filters and exclusions
null and zero treatment
unit
rounding
expected fixture result
```

Las agregaciones porcentuales deberán usar ratio de sumas cuando corresponda; no se aceptará el promedio simple de porcentajes por fila sin justificación contractual.

---

## 10. Power BI

El dashboard V1.0 tendrá cuatro páginas.

### Executive

Visión global de:

```text
Sales
MC_CTS
CTS
OTIF
Fill Rate
Orders
Customers
```

### Customer 360

Permitir seleccionar un cliente y visualizar:

```text
sales
orders
SKU mix
frequency
service
CTS
MC_CTS
```

### Service & Inventory

Analizar:

```text
OTIF
Fill Rate
Lead Time
stockouts
inventory
SKU
```

### Profitability & Geography

Analizar:

```text
customer profitability
CTS
delivery cost
distance
geographical distribution
```

Debe existir al menos una visualización cartográfica.

Comportamiento mínimo:

- una única dimensión calendario gobernará los filtros de período;
- Customer 360 permitirá seleccionar un cliente y filtrar pedidos, entregas, servicio, CTS y rentabilidad;
- las páginas mostrarán la última ejecución exitosa y el estado de calidad del dataset;
- los totales visibles deberán reconciliar con tablas de control calculadas fuera de Power BI;
- no se usarán relaciones many-to-many salvo excepción documentada y aprobada;
- la lógica de validación, clasificación de servicio, CTS y KPIs permanecerá aguas arriba o en medidas documentadas, nunca dispersa en visuales.

---

## 11. Arquitectura de V1.0 Core

```text
Contracts + Configuration
  ↓
Python Generator
  ↓
Synthetic Data
  ↓
Validation / QC
  ↓
Validated Canonical Tables
  ↓
Analytical Marts
  ↓
Star Schema
  ↓
Power BI Desktop
```

Power BI no será la fuente maestra de reglas de negocio.

Cada ejecución end-to-end deberá emitir un manifiesto y reporte de calidad. CSV y Parquet serán formatos de intercambio; DuckDB será opcional y no podrá convertirse en dependencia oculta.

---

## 12. Herramientas de V1.0 Core

### Core

```text
Markdown
Python
pandas
pytest
CSV / Parquet
Power BI Desktop
```

### Opcional

```text
DuckDB
Jupyter
```

Git está habilitado por autorización explícita del usuario. La reproducibilidad
continúa dependiendo de configuración, semilla, versiones, pruebas y hashes, no
del historial Git.

No forman parte de V1.0 Core:

```text
ERPNext
CRM
n8n
PostgreSQL
dbt
StatsForecast
SciPy
Statsmodels
OSRM
VROOM
OR-Tools
```

---

## 13. Reproducibilidad

El dataset final deberá poder regenerarse mediante código.

La generación deberá registrar como mínimo:

```yaml
scenario_id: "B2B-V1-BASE"
data_class: "synthetic"
seed: 20260813
generator_version: "definida por la implementación"
schema_version: "definida en DATA-CONTRACT.md"
config_sha256: "calculado en ejecución"
run_id: "calculado en ejecución"
```

La misma configuración, semilla, versión de generador y versión de esquema deberá producir los mismos IDs, filas, valores ordenados y totales de control.

El manifiesto de ejecución registrará:

```text
timestamps
input and output paths
row counts
rejected row counts and reasons
artifact checksums
quality results
execution status
sanitized error, if any
```

---

## 14. Criterios de aceptación

V1.0 Core cumplirá esta especificación cuando:

```text
[ ] un comando documentado regenere B2B-V1-BASE con exit code 0
[ ] clientes, SKU, vehículos y sitios coincidan con sus cantidades exactas
[ ] pedidos y líneas estén dentro de sus tolerancias
[ ] la repetición con misma configuración produzca los mismos checksums
[ ] existan 0 PK nulas o duplicadas y 0 FK huérfanas
[ ] existan 0 violaciones de cantidades, costos y secuencia temporal
[ ] se cumplan los gates de cobertura sintética de la sección 3
[ ] pueda reconstruirse un pedido con todas sus líneas, entregas y costos sin duplicación
[ ] fixtures conocidos reproduzcan OTIF, Fill Rate, CTS y MC_CTS esperados
[ ] todos los KPIs mínimos tengan prueba de reconciliación
[ ] Power BI actualice desde los marts sin transformación estructural oculta
[ ] Customer 360 filtre de cliente a pedido, entrega, servicio, CTS y MC_CTS
[ ] exista una vista geográfica con coordenadas válidas y sintéticas/referenciales
[ ] pueda compararse servicio y rentabilidad en un mismo contexto de cliente
[ ] el manifiesto y reporte QA identifiquen la ejecución y sus artefactos
```

La validación deberá incluir pruebas positivas y negativas. Un validador que sólo pasa con datos correctos pero no rechaza fixtures deliberadamente inválidos no satisface la aceptación.

---

## 15. Fuera de alcance

V1.0 Core no requiere:

```text
datos corporativos reales
mensajería real
telefonía real
cotización productiva
facturación y pagos
crédito de cliente
devoluciones y notas de crédito
reclamos productivos
forecasting productivo
optimización VRP
machine learning
ERP
CRM
automatización n8n
despliegue cloud
TDABC avanzado
Hypothesis Lab
feedback automatizado
```

Estas funciones podrán incorporarse después de aprobar V1.0 mediante nuevos contratos y criterios de aceptación.

---

## 16. Siguiente artefacto

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

La generación, validación, marts y construcción manual de Power BI fueron
ejecutadas y aceptadas como V1.0. No se autoriza ampliar este alcance sin un
contrato post-V1 explícito.

---

## 17. Registro de cambios

|Fecha|Versión documento|Estado|Cambio|
|---|---|---|---|
|2026-08-13|0.1|draft|Borrador previo al trabajo con Codex.|
|2026-08-13|0.2|approved|Se especifican y aprueban escenario base, cardinalidades funcionales, servicio, inventario, reconocimiento económico, reproducibilidad y aceptación de V1.0 Core.|
|2026-08-16|0.3|approved|Se sincroniza la especificación con el estado RELEASE_CANDIDATE y el cierre de implementación, manteniendo pendientes los gates finales de Power BI.|
|2026-08-16|0.4|approved|El usuario acepta el PBIX manual, cierra PBI-04/PBI-05 y promueve la especificación implementada a V1.0.|
