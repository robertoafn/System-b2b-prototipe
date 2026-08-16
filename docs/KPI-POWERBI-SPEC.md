---
doc_id: "MVP-D03"
title: "V1.0 KPI and Power BI Specification"
version: "0.3"
status: "approved"
type: "analytics_specification"
created: "2026-08-13"
updated: "2026-08-16"
depends_on:
  - "MVP-D01"
  - "MVP-D02"
---

# V1.0 KPI and Power BI Specification

## 1. Objetivo

Definir el modelo estrella, las medidas computables, los contextos de filtro y el diseño funcional de las cuatro páginas Power BI de V1.0 Core.

La métrica primaria es `MC_CTS`. Net Sales, Contribution Margin y CTS explican su movimiento; OTIF, Fill Rate y Stockout Rate actúan como guardrails de servicio e inventario.

No se fijan metas empresariales en V1.0 porque el dataset es sintético y no existe baseline operacional real. Los umbrales de D01/D02 son gates de cobertura y calidad, no objetivos de negocio.

## 2. Modelo estrella

### 2.1 Dimensiones conformadas

|Tabla|Grain|Clave|Uso|
|---|---|---|---|
|`dim_customer`|1 cliente|`customer_key`|segmento y Customer 360|
|`dim_product`|1 SKU|`product_key`|familia, unidad y mix|
|`dim_location`|1 ubicación|`location_key`|comuna, región y mapa|
|`dim_operational_site`|1 sitio|`site_key`|inventario y origen|
|`dim_vehicle`|1 vehículo|`vehicle_key`|capacidad y utilización|
|`dim_date`|1 fecha|`date_key`|calendario único|

Las dimensiones tendrán surrogate key entera y conservarán el identificador contractual como business key.

### 2.2 Hechos

|Tabla|Grain|Propósito|
|---|---|---|
|`fact_orders`|1 pedido|resultado de servicio y economía reconciliada por pedido|
|`fact_order_lines`|1 línea de pedido|demanda, precio, cantidad pedida y cantidad entregada acumulada|
|`fact_deliveries`|1 evento de entrega|distancia, vehículo, carga y fechas|
|`fact_delivery_lines`|1 línea de pedido incluida en 1 entrega|cantidad y economía reconocida por SKU|
|`fact_inventory`|1 fecha × sitio × SKU|snapshot diario de inventario|
|`fact_cost_to_serve`|1 actividad de costo|detalle CTS y driver|

`fact_orders` contendrá los totales reconciliados `recognized_net_sales`, `variable_product_cost`, `contribution_margin`, `cts_amount` y `mc_cts_amount`. El detalle debe cuadrar con `fact_delivery_lines` y `fact_cost_to_serve`.

Columnas analíticas mínimas adicionales:

|Fact|Claves/fechas|Medidas y flags mínimos|
|---|---|---|
|`fact_orders`|order, customer, location, order/promised/completion date|eligible, in-full, on-time, OTIF, service class, quantities, lead time, economía reconciliada|
|`fact_order_lines`|order line, order, customer, product, location, order/promised date|ordered quantity, delivered quantity, list/net price, ordered net sales|
|`fact_deliveries`|delivery, order, customer, location, site, vehicle, order/dispatch/delivery/promised date|distance, delivered weight/volume, capacities, weight/volume utilization|
|`fact_delivery_lines`|delivery line, delivery, order line, order, customer, product, location, site, vehicle, order/delivery/promised date|delivered quantity, recognized net sales, variable cost, contribution margin|
|`fact_inventory`|snapshot date, site, product|on-hand, allocated, available, safety stock, reorder point, stockout/low flags|
|`fact_cost_to_serve`|cost activity, order, optional delivery, customer, location, optional vehicle, order/activity/delivery date|cost type, amount, driver, allocation method|

### 2.3 Relaciones

Reglas obligatorias:

```text
dimension 1 → N fact
filter direction = single
facts do not relate directly to other facts
no many-to-many relationships
one and only one dim_date
```

Matriz de relaciones activas no temporales:

|Dimensión|Facts relacionados|
|---|---|
|`dim_customer`|orders, order_lines, deliveries, delivery_lines, cost_to_serve|
|`dim_product`|order_lines, delivery_lines, inventory|
|`dim_location`|orders, deliveries, delivery_lines, cost_to_serve|
|`dim_operational_site`|deliveries, delivery_lines, inventory|
|`dim_vehicle`|deliveries, delivery_lines; cost_to_serve cuando exista entrega|

Las claves de dimensión opcionales en `fact_cost_to_serve` podrán ser `Unknown/Not applicable`, nunca FK huérfanas.

Los IDs `order_id`, `order_line_id` y `delivery_id` se conservarán como dimensiones degeneradas para trazabilidad y drill-through, no como relaciones entre hechos.

### 2.4 Roles de fecha

|Hecho|Relación activa|Relaciones inactivas/alternativas|
|---|---|---|
|`fact_orders`|`order_date_key`|`promised_date_key`, `completion_date_key`|
|`fact_order_lines`|`order_date_key`|`promised_date_key`|
|`fact_deliveries`|`delivery_date_key`|`order_date_key`, `dispatch_date_key`, `promised_date_key`|
|`fact_delivery_lines`|`order_date_key`|`delivery_date_key`, `promised_date_key`|
|`fact_inventory`|`snapshot_date_key`|ninguna|
|`fact_cost_to_serve`|`order_date_key`|`activity_date_key`, `delivery_date_key`|

Medidas de servicio por compromiso utilizarán `promised_date_key`. Las medidas económicas utilizarán `order_date_key`. Tendencias físicas de entregas utilizarán `delivery_date_key`.

### 2.5 Seguridad de agregación

- `fact_inventory` es semi-aditivo en el tiempo y nunca se suma entre fechas.
- CTS se suma desde una actividad única o desde el total reconciliado por pedido, nunca desde ambos a la vez.
- `MC_CTS` es válido por pedido, cliente, ubicación de cliente y período de pedido.
- `MC_CTS` no es válido por SKU en V1.0 porque CTS no se asigna a producto.
- Una medida MC_CTS bajo filtro de producto deberá retornar `BLANK()` para evitar una atribución falsa.

### 2.6 Tablas técnicas desconectadas

|Tabla|Grain|Uso|
|---|---|---|
|`meta_run`|1 fila para el build cargado|build ID, ejecución, fechas máximas, checksums y estado QA|
|`qa_results`|1 fila por quality gate|nombre, estado, violaciones y mensaje sanitizado|

Estas tablas provienen del manifiesto/reporte QA y no participan en relaciones del modelo estrella.

## 3. KPIs

### 3.1 Jerarquía de medición

|Rol|Métricas|Decisión|
|---|---|---|
|Primary outcome|MC_CTS|priorizar clientes y políticas con contribución económica después de servir|
|Value drivers|Net Sales, Contribution Margin, CTS|explicar el resultado económico|
|Guardrails|OTIF, Fill Rate, Stockout Rate|evitar interpretar ahorro o margen con deterioro de servicio|
|Diagnostics|Orders, AOV, Lead Time, Inventory, Frequency, Distance, Transport Cost, Vehicle Utilization, Customers|localizar causas y segmentos|

### 3.2 Convenciones de medida

```text
percentage storage = decimal in [0,1]
percentage display = 0.0%
currency display = CLP with 2 decimals
distance = km
lead time = hours
zero denominator = BLANK, never 0 or infinity
missing observation = BLANK unless contract defines zero
```

Los pedidos elegibles y las cuatro clases de servicio siguen D01. Los pedidos cancelados no se generan en `B2B-V1-BASE`.

### 3.3 Diccionario computable

|ID|KPI|Fórmula contractual|Fuente oficial|Fecha|Grain válido|
|---|---|---|---|---|---|
|KPI-01|Net Sales|`SUM(recognized_net_sales)`|`fact_orders`|order date|pedido, cliente, ubicación, período|
|KPI-02|Variable Product Cost|`SUM(variable_product_cost)`|`fact_orders`|order date|pedido, cliente, ubicación, período|
|KPI-03|Contribution Margin|`Net Sales - Variable Product Cost`|medidas KPI-01/02|order date|pedido, cliente, ubicación, período|
|KPI-04|CTS|`SUM(cts_amount)`|`fact_orders`|order date|pedido, cliente, ubicación, período|
|KPI-05|MC_CTS|`Contribution Margin - CTS`|medidas KPI-03/04|order date|pedido, cliente, ubicación, período; no SKU|
|KPI-06|Orders|`DISTINCTCOUNT(order_id)`|`fact_orders`|order date|cliente, ubicación, período|
|KPI-07|Average Order Value|`Net Sales / Orders`|KPI-01/06|order date|cliente, ubicación, período|
|KPI-08|OTIF|`OTIF Orders / Eligible Orders`|`fact_orders`|promised date|pedido, cliente, ubicación, período|
|KPI-09|Fill Rate|`SUM(delivered_quantity) / SUM(ordered_quantity)`|`fact_order_lines`|promised date|SKU, cliente, ubicación, período|
|KPI-10|Order-to-Delivery Lead Time|`AVERAGE(lead_time_hours)` para pedidos completos|`fact_orders`|promised date|cliente, ubicación, período|
|KPI-11|Stockout Rate|`Stockout Observations / Inventory Observations`|`fact_inventory`|snapshot date|SKU, sitio, período|
|KPI-12|Available Inventory EOP|inventario disponible en la última fecha visible|`fact_inventory`|snapshot date|SKU, sitio, fecha de cierre|
|KPI-13|Customer Frequency|`Orders / Customers`|KPI-06/17|order date|segmento, ubicación, período|
|KPI-14|Delivery Distance|`SUM(distance_km)`|`fact_deliveries`|delivery date|vehículo, cliente, ubicación, período|
|KPI-15|Transport Cost|`SUM(cost_amount)` donde `cost_type = transport`|`fact_cost_to_serve`|order date|pedido, cliente, ubicación, período|
|KPI-16|Vehicle Utilization|promedio del recurso limitante por entrega|`fact_deliveries`|delivery date|vehículo, período|
|KPI-17|Customers|clientes distintos con al menos un pedido|`fact_orders`|order date|segmento, ubicación, período|

### 3.4 Reglas detalladas

**Net Sales y economía por SKU**

La medida oficial ejecutiva usa `fact_orders`. Para mix y detalle de SKU se utilizará:

```text
Net Sales by SKU
=
SUM(fact_delivery_lines.recognized_net_sales)
```

Sin filtro de producto deberá reconciliar exactamente con KPI-01. Contribution Margin by SKU se permite; CTS y MC_CTS by SKU no se permiten en V1.0.

```text
MC_CTS
=
IF(
  product filter is active,
  BLANK(),
  Contribution Margin - CTS
)
```

**OTIF**

```text
Eligible Orders
=
COUNTROWS(fact_orders where eligible_order_flag = true)

OTIF Orders
=
COUNTROWS(fact_orders where eligible_order_flag = true and order_otif_flag = true)

OTIF
=
DIVIDE(OTIF Orders, Eligible Orders)
```

El filtro temporal usa fecha prometida. El filtro SKU no modifica el OTIF oficial.

**Fill Rate**

```text
Fill Rate
=
DIVIDE(
  SUM(fact_order_lines.delivered_quantity),
  SUM(fact_order_lines.ordered_quantity)
)
```

Se calcula como ratio de sumas, nunca como promedio de ratios por línea.

**Lead Time**

```text
lead_time_hours
=
completion_datetime - order_datetime
```

Sólo pedidos `in_full` tienen lead time oficial. Pedidos incompletos permanecen `BLANK()` y se controlan mediante Fill Rate y clases de servicio.

**Available Inventory EOP**

```text
last_visible_date = MAX(dim_date[date])

Available Inventory EOP
=
SUM(fact_inventory.available_quantity at last_visible_date)
```

No sumar snapshots entre fechas.

**Vehicle Utilization**

```text
weight_utilization = delivered_weight_kg / capacity_kg
volume_utilization = delivered_volume_m3 / capacity_m3
delivery_utilization = MAX(weight_utilization, volume_utilization)
Vehicle Utilization = AVERAGE(delivery_utilization)
```

Los porcentajes de peso y volumen deberán exponerse también como diagnósticos para mostrar cuál capacidad limita cada entrega.

### 3.5 Restricciones de interpretación

- KPIs sintéticos demuestran funcionamiento, no desempeño real.
- MC_CTS no es margen neto.
- OTIF no se promedia desde líneas.
- Fill Rate no prueba puntualidad.
- Stockout Rate depende de la cadencia diaria del contrato.
- AOV usa todos los pedidos del período; pedidos sin entrega aportan cero ventas reconocidas.
- Customers representa clientes con pedidos, no el total maestro de 150.

## 4. Dashboard

### 4.1 Brief

```yaml
surface: "Power BI Desktop"
mode: "local analytical dashboard"
primary_audience:
  - Management
  - Commercial
  - Operations
review_cadence: "monthly, with exploratory drill-through"
data_source: "validated analytical marts"
source_parameter: "pDataRoot"
```

Cada página mostrará `dataset_build_id`, última ejecución exitosa, fecha máxima disponible y estado QA. Power BI no consumirá archivos de snapshot o scratch fuera de los marts aprobados.

Filtros globales permitidos: período, segmento de cliente y región. Filtros adicionales se limitan a la página donde sean semánticamente válidos.

### Page 1 — Executive

**Pregunta:** ¿cómo evoluciona el resultado económico y qué guardrails requieren atención?

Hero cards:

```text
MC_CTS
Net Sales
CTS
OTIF
Fill Rate
Orders
Customers
```

Visuales:

|Visual|Tipo|Campos|Lectura|
|---|---|---|---|
|Economía mensual|líneas, 12 meses|Net Sales, MC_CTS, mes|movimiento económico|
|Servicio mensual|líneas, 12 meses|OTIF, Fill Rate, mes|guardrails comparables|
|Clientes por MC_CTS|barras horizontales ordenadas|customer, MC_CTS|top y bottom con cero visible|

Los indicadores no usarán colores de cumplimiento contra metas inexistentes. Sólo el estado QA podrá usar semáforo explícito.

### Page 2 — Customer 360

**Pregunta:** ¿qué valor, servicio y costo explican la situación de un cliente?

Filtro obligatorio: un cliente. Si no existe selección, la página mostrará una instrucción y no una falsa vista agregada.

Hero cards:

```text
Net Sales
Contribution Margin
CTS
MC_CTS
Orders
Customer Frequency
OTIF
Fill Rate
Lead Time
```

Visuales:

|Visual|Tipo|Campos|Lectura|
|---|---|---|---|
|Economía del cliente|líneas mensuales|Net Sales, Contribution Margin, CTS, MC_CTS|evolución y presión de servicio|
|Mix SKU|barras horizontales|SKU, Net Sales by SKU|composición reconocida|
|Servicio por pedido|tabla de detalle|order_id, promise, completion, class, Fill Rate, CTS, MC_CTS|lookup y drill-through|

No mostrar `MC_CTS by SKU`.

### Page 3 — Service & Inventory

**Pregunta:** ¿dónde se originan incumplimientos y riesgo de inventario?

Filtros: período, sitio y SKU. El filtro SKU no afectará el OTIF oficial; esa tarjeta y su tendencia deberán indicarlo en el subtítulo.

Hero cards:

```text
OTIF
Fill Rate
Average Lead Time
Stockout Rate
Available Inventory EOP
```

Visuales:

|Visual|Tipo|Campos|Lectura|
|---|---|---|---|
|Servicio mensual|líneas|OTIF, Fill Rate, promised month|movimiento con denominador visible|
|Fill Rate por SKU|barras horizontales ordenadas|SKU, Fill Rate, ordered quantity|comparación con volumen|
|Stockout SKU × mes|heatmap|SKU, mes, Stockout Rate|patrones densos|
|Inventario seleccionado|línea diaria|available, safety stock, reorder point, date|trayectoria y umbrales|
|Clases de servicio|barra 100% apilada|complete/partial × on-time/late|composición de pedidos elegibles|

### Page 4 — Profitability & Geography

**Pregunta:** ¿qué clientes y zonas combinan valor, costo y distancia de manera desfavorable?

Filtros: período, segmento, región y comuna.

Hero cards:

```text
MC_CTS
CTS
Transport Cost
Delivery Distance
Vehicle Utilization
```

Visuales:

|Visual|Tipo|Campos|Lectura|
|---|---|---|---|
|Mapa de clientes|mapa de puntos|lat/lon, Net Sales, MC_CTS, customer|distribución territorial|
|Ventas vs CTS|scatter a grain cliente|Net Sales, CTS, segment, customer|relación, clusters y outliers|
|MC_CTS por cliente|barras horizontales ordenadas|customer, MC_CTS|ranking con cero visible|
|Rentabilidad y logística|tabla|customer, Net Sales, CTS, MC_CTS, distance, transport cost, OTIF|seguimiento exacto|

El scatter requiere al menos 20 clientes visibles; con menos de 8 se reemplazará por tabla o barras. El mapa usará tamaño por Net Sales y una codificación divergente restringida para el signo de MC_CTS, sin semántica rojo/verde.

### 4.2 Diseño visual transversal

- jerarquía: hero metrics → tendencia → diagnóstico → detalle;
- fondos claros, texto oscuro y grillas discretas;
- una raíz cromática para series simples y máximo dos para valores con signo;
- no depender exclusivamente del color: usar etiquetas, orden, cero y tooltips;
- barras de magnitud parten en cero;
- títulos descriptivos y subtítulos con unidad, período y denominador;
- mínimo 8–12 puntos para líneas temporales;
- tablas sólo para lookup, trazabilidad o detalle operativo.

## 5. Regla

Power BI consume tablas analíticas.

La lógica estructural y validación debe resolverse antes de Power BI.

### 5.1 Modelo semántico

- las medidas residirán en una tabla dedicada `_Measures`;
- display folders: `Economic`, `Commercial`, `Service`, `Inventory`, `Logistics`, `Quality`;
- claves técnicas y columnas auxiliares permanecerán ocultas;
- nombres de medidas seguirán este documento y no crearán sinónimos divergentes;
- no se crearán columnas calculadas para reemplazar transformaciones del pipeline;
- DAX se limitará a agregación, contextos de filtro, roles de fecha y presentación;
- no habrá relaciones bidireccionales, many-to-many ni rutas ambiguas;
- no se requiere RLS en V1.0 porque todos los datos son sintéticos.

### 5.2 Trazabilidad

Cada medida deberá registrar:

```text
KPI ID
measure name
source fact
numerator and denominator
date role
valid dimensions
format
Python control value
```

`fact_orders` será la tabla oficial de reconciliación económica por pedido. Los facts detallados deberán sumar los mismos totales sin duplicación.

## 6. Acceptance

### 6.1 Modelo y refresh

```text
[ ] b2b_v1.pbix abre sin error
[ ] pDataRoot permite apuntar a una reconstrucción local limpia
[ ] refresh completa desde marts validados
[ ] relaciones dimensión 1:N y filtro single
[ ] cero relaciones many-to-many o bidireccionales
[ ] cero rutas de filtro ambiguas
[ ] una única dim_date con rango completo
[ ] surrogate y business keys de dimensiones son únicas
[ ] cada fact conserva su grain sin duplicados
[ ] conteos de pedidos, líneas, entregas, costos e inventario reconcilian con marts
[ ] business keys visibles para drill-through y surrogate keys ocultas
```

### 6.2 Medidas

```text
[x] los 17 KPI y las 2 medidas de soporte tienen medida documentada
[ ] importes cuadran con Python a 0,01 CLP
[ ] cantidades cuadran a 0,001 unidades
[ ] ratios cuadran con tolerancia absoluta 1e-9
[ ] denominador cero retorna BLANK
[ ] Net Sales by SKU reconcilia con Net Sales sin filtro de producto
[ ] CTS detallado reconcilia con fact_orders
[ ] MC_CTS = Net Sales - Variable Product Cost - CTS
[ ] MC_CTS retorna BLANK bajo filtro de producto
[ ] OTIF usa pedidos elegibles y fecha prometida
[ ] Fill Rate usa ratio de sumas
[ ] inventario usa última fecha visible, no suma snapshots
[ ] fixtures golden producen resultados esperados
```

### 6.3 Experiencia de uso

```text
[ ] existen exactamente cuatro páginas Core
[ ] vista inicial responde sin interacción obligatoria, excepto Customer 360
[ ] Customer 360 exige un cliente y filtra economía, servicio y pedidos
[ ] filtros de período, segmento y geografía son consistentes
[ ] alcance del filtro SKU está indicado donde no aplica a OTIF o MC_CTS
[ ] mapa usa coordenadas válidas y muestra procedencia sintética/referencial
[ ] drill-through rastrea customer → order → delivery → CTS → MC_CTS
[ ] todas las páginas muestran build, freshness y QA
[ ] no existen visuales decorativos o sin pregunta de decisión
```

No comenzar la construcción definitiva del `.pbix` antes de aprobar D03 y producir marts validados.

---

## 7. Estado

```yaml
PROJECT_PROGRESS:
  target_release: "V1.0"
  release_status: "RELEASE_CANDIDATE"
  stage: "RELEASE_HARDENING"
  current_work_item: "V1.0-CLOSEOUT"
  status: "IN_PROGRESS"
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
  next: "PBI-04 final visual proof and PBI-05 acceptance"
  blockers:
    - "Power BI Desktop must export PBIP/PBIR"
```

---

## 8. Registro de cambios

|Fecha|Versión documento|Estado|Cambio|
|---|---|---|---|
|2026-08-13|0.1|draft|Borrador previo al trabajo con Codex.|
|2026-08-13|0.2|approved|Se completa y aprueba modelo estrella, diccionario KPI, roles de fecha, filtros, páginas, diseño visual y acceptance de Power BI V1.0.|
|2026-08-16|0.3|approved|Se registra la construcción y reconciliación de 17 KPI, 2 medidas de soporte y 20 auxiliares; el release permanece candidato hasta cerrar PBI-04 y PBI-05.|
