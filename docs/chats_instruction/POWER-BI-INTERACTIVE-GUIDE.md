---
doc_id: "PBI-CHAT-01"
title: "Guía interactiva ChatGPT + Power BI — V1.0 Core"
version: "3.15"
status: "released_v1_0_0"
created: "2026-08-14"
updated: "2026-08-16"
depends_on:
  - "MVP-D03"
  - "MVP-I04"
---

# Guía interactiva ChatGPT + Power BI — V1.0 Core

## 1. Propósito

Este documento permite construir manualmente en Power BI Desktop el modelo semántico, las medidas y las cuatro páginas Core del proyecto:

C:\b2b-commercial-operational-system

ChatGPT actúa como copiloto. La persona usuaria ejecuta cada acción en Power BI, devuelve el resultado y sólo entonces avanza al siguiente checkpoint.

Este archivo es una bitácora viva. Codex deberá actualizar su sección de estado cuando la persona usuaria comparta evidencia verificable de Power BI.

## 2. Forma de uso

1. Abrir Power BI Desktop.
2. Guardar o trabajar sobre:

C:\b2b-commercial-operational-system\powerbi\b2b_v1.pbix

3. Adjuntar este Markdown a un chat nuevo de ChatGPT o copiar el prompt maestro de la sección 3.
4. Indicar a ChatGPT el checkpoint que se desea ejecutar.
5. Realizar manualmente las acciones en Power BI.
6. Devolver a ChatGPT los valores, errores o capturas solicitados.
7. No avanzar cuando el checkpoint indique FAILED o exista una diferencia no explicada.
8. Para actualizar esta bitácora en el repositorio, volver a Codex y escribir:

Actualizar guía Power BI con el resultado del checkpoint PBI-XX: [resultado]

ChatGPT fuera de Codex puede orientar, pero no puede actualizar por sí mismo este archivo local.

## 3. Prompt maestro para ChatGPT

Copiar desde INICIO DEL PROMPT hasta FIN DEL PROMPT.

### INICIO DEL PROMPT

Actúa como copiloto experto de Power BI Desktop para el proyecto local B2B V1.0 Core.

Tu misión es guiarme manualmente, un checkpoint a la vez, para construir y validar:

1. carga de 14 marts Parquet;
2. modelo estrella con relaciones controladas;
3. tabla dedicada de medidas;
4. 17 KPI, 2 medidas de soporte y 20 medidas auxiliares;
5. exactamente cuatro páginas Core;
6. reconciliación contra controles Python;
7. guardado final de b2b_v1.pbix.

Reglas obligatorias:

- Usa como fuente de verdad este documento y no inventes tablas, columnas, KPI, metas ni relaciones.
- Trabaja en una sola fase por respuesta.
- No avances hasta que yo confirme el resultado del checkpoint actual.
- En cada respuesta usa esta estructura:
  - Objetivo
  - Acciones exactas en Power BI
  - Resultado esperado
  - Evidencia que debo devolverte
  - Decisión PASS o FAIL
- Si los nombres de menús difieren por idioma o versión, adapta la ruta sin cambiar la semántica.
- Si aparece un error, diagnostícalo antes de proponer cambios.
- No sugieras relaciones many-to-many, bidireccionales o entre facts.
- No permitas más de una dim_date.
- No crees columnas calculadas para reconstruir lógica estructural.
- DAX sólo puede resolver agregación, contexto de filtro, roles de fecha y presentación.
- No atribuyas CTS ni MC_CTS a SKU.
- MC_CTS debe devolver BLANK bajo filtro de producto.
- OTIF debe usar pedido elegible y fecha prometida.
- Fill Rate debe ser ratio de sumas, nunca promedio de ratios.
- Inventario EOP debe usar la última fecha visible, nunca sumar snapshots.
- Los datos son sintéticos; nunca los presentes como desempeño real.
- No uses data/synthetic ni data/validated. Power BI consume solamente data/marts.
- No declares el dashboard terminado basándote sólo en una captura. Exige las validaciones de este documento.
- No realices operaciones Git desde este chat manual; el versionado se gestiona fuera de Power BI.

Contexto fijo:

- Repositorio: C:\b2b-commercial-operational-system
- Archivo Power BI objetivo: C:\b2b-commercial-operational-system\powerbi\b2b_v1.pbix
- Parámetro Power Query: pDataRoot
- Valor de pDataRoot: C:\b2b-commercial-operational-system\data\marts
- Build: BLD-9102B6E8BF1ABFFC5F32
- Ejecución marts: MRT-F0A43B2880354EEC8662EE6A1113D26A
- QA de fuente: 93/93
- QA de marts: 91/91
- Tablas Parquet: 14
- Medidas: 17 KPI + 2 de soporte + 20 auxiliares = 39
- Moneda: CLP neta de IVA
- Zona horaria contractual: America/Santiago
- Período base: 2025-08-01 a 2026-07-31

Empieza preguntándome por el checkpoint indicado. Si no indico uno, comienza en PBI-00.

### FIN DEL PROMPT

## 4. Estado interactivo

| Checkpoint | Resultado esperado                | Estado  | Evidencia                                                                                                                                                   |
| ---------- | --------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PBI-00     | Archivo guardado y opciones base  | PASSED  | b2b_v1.pbix guardado; en Archivo actual, Auto date/time y las tres opciones de Relaciones están desactivadas; ValueFilterBehavior Independiente conservado. |
| PBI-01     | 14 marts cargados desde pDataRoot | PASSED  | 14 tablas aplicadas sin errores y conteos reconciliados. PBIX guardado: 2.588.451 bytes, 2026-08-14 22:51:33.                                               |
| PBI-02     | Modelo estrella con 34 relaciones | PASSED  | Validado en Power BI: 34 relaciones totales, 24 activas y 10 inactivas; sin relaciones para meta_run ni qa_results.                                         |
| PBI-03     | 39 medidas creadas y reconciliadas | PASSED | 17 KPI, 2 medidas de soporte y 20 auxiliares; sin errores DAX; QA Failed Gates=0, QA Status=passed; pruebas sin filtro y con SKU reconciliadas. |
| PBI-04     | Cuatro páginas Core construidas   | PASSED | Las cuatro páginas están funcionales, guardadas y documentadas con capturas; el usuario acepta el resultado manual de Power BI Desktop para V1.0. |
| PBI-05     | Refresh, experiencia y aceptación | PASSED | El usuario confirma y acepta el PBIX construido y guardado manualmente en Power BI Desktop como artefacto final de V1.0. |

Estados válidos:

- PENDING: no ejecutado.
- IN_PROGRESS: iniciado sin evidencia completa.
- PASSED: evidencia reconciliada.
- FAILED: existe error o diferencia pendiente.
- BLOCKED: requiere una decisión o recurso no disponible.

Estado de release: `V1.0`. PBI-04 y PBI-05 están en `PASSED` por aceptación
explícita del usuario; corresponde publicar el tag y GitHub Release `v1.0.0`.

## 5. Fuente aprobada y controles

### 5.1 Única carpeta de carga

C:\b2b-commercial-operational-system\data\marts

No combinar todos los Parquet como si tuvieran el mismo esquema. Cada archivo representa una tabla distinta.

### 5.2 Tablas y filas esperadas

|Tabla|Filas|
|---|---:|
|dim_customer|150|
|dim_product|30|
|dim_location|151|
|dim_operational_site|1|
|dim_vehicle|7|
|dim_date|365|
|fact_orders|4.000|
|fact_order_lines|10.000|
|fact_deliveries|5.000|
|fact_delivery_lines|12.483|
|fact_inventory|10.950|
|fact_cost_to_serve|22.165|
|meta_run|1|
|qa_results|184|

dim_vehicle contiene seis vehículos sintéticos más el miembro técnico N/A con vehicle_key = 0.

### 5.3 Valores Python de control

|KPI|Valor exacto de control|Formato visible|
|---|---:|---|
|Net Sales|14.486.600.352,07|CLP, 2 decimales|
|Variable Product Cost|8.849.398.967,32|CLP, 2 decimales|
|Contribution Margin|5.637.201.384,75|CLP, 2 decimales|
|CTS|2.082.958.305,74|CLP, 2 decimales|
|MC_CTS|3.554.243.079,01|CLP, 2 decimales|
|Orders|4.000|entero|
|Average Order Value|3.621.650,0880175|CLP, 2 decimales visibles|
|OTIF|0,7|70,0%|
|Fill Rate|0,9257752874732879|92,6%|
|Order-to-Delivery Lead Time|94,8175|horas|
|Stockout Rate|0,02009132420091324|2,0%|
|Available Inventory EOP|3.573|unidades|
|Customer Frequency|26,666666666666668|2 decimales visibles|
|Delivery Distance|269.600,965|km|
|Transport Cost|1.748.790.794,13|CLP, 2 decimales|
|Vehicle Utilization|0,028494594187178403|2,8%|
|Customers|150|entero|

Tolerancias:

- moneda: 0,01 CLP;
- cantidad: 0,001 unidades;
- ratio: tolerancia absoluta 1e-9;
- denominador cero: BLANK.

## 6. PBI-00 — preparar el archivo

### Acciones

1. Guardar como:

C:\b2b-commercial-operational-system\powerbi\b2b_v1.pbix

2. En las opciones del archivo actual, desactivar Auto date/time.
3. Confirmar que el modo de almacenamiento será Import.
4. No activar RLS.
5. En `Archivo actual > Carga de datos > Relaciones`, dejar desactivadas las tres opciones: importar relaciones en la primera carga, actualizar o eliminar relaciones al actualizar y detectar automáticamente nuevas relaciones al cargar. Si ya se creó alguna relación, eliminarla antes de PBI-02.
6. Mantener activada la opción ValueFilterBehavior = Independent. Este comportamiento conserva separados los filtros sobre columnas de una misma tabla.

### Evidencia a devolver

~~~~text
CHECKPOINT PBI-00
archivo: C:\b2b-commercial-operational-system\powerbi\b2b_v1.pbix
auto_date_time: disabled
storage_mode: Import
import_source_relationships_first_load: disabled
update_or_delete_relationships_on_refresh: disabled
auto_relationships: disabled
errors: none
~~~~

### Gate

PASS sólo si el archivo está guardado en la ruta indicada y no existen relaciones automáticas que puedan contaminar el modelo.

## 7. PBI-01 — cargar los 14 marts

### 7.1 Crear pDataRoot

Abrir Transform data y, en Power Query:

1. Manage Parameters.
2. New Parameter.
3. Nombre: pDataRoot.
4. Tipo: Text.
5. Required: Yes.
6. Current Value:

C:\b2b-commercial-operational-system\data\marts

### 7.2 Crear la función fnLoadParquet

Crear una Blank Query, abrir Advanced Editor y reemplazar el contenido por:

~~~~powerquery
(fileName as text) as table =>
let
    FullPath = pDataRoot & "\" & fileName,
    Source = Parquet.Document(File.Contents(FullPath))
in
    Source
~~~~

Renombrar la consulta como fnLoadParquet y desactivar Enable load.

### 7.3 Crear cada tabla

Para cada fila siguiente, crear una Blank Query, pegar su expresión y usar exactamente el nombre de tabla indicado.

|Nombre consulta|Expresión M|
|---|---|
|dim_customer|fnLoadParquet("dim_customer.parquet")|
|dim_product|fnLoadParquet("dim_product.parquet")|
|dim_location|fnLoadParquet("dim_location.parquet")|
|dim_operational_site|fnLoadParquet("dim_operational_site.parquet")|
|dim_vehicle|fnLoadParquet("dim_vehicle.parquet")|
|dim_date|fnLoadParquet("dim_date.parquet")|
|fact_orders|fnLoadParquet("fact_orders.parquet")|
|fact_order_lines|fnLoadParquet("fact_order_lines.parquet")|
|fact_deliveries|fnLoadParquet("fact_deliveries.parquet")|
|fact_delivery_lines|fnLoadParquet("fact_delivery_lines.parquet")|
|fact_inventory|fnLoadParquet("fact_inventory.parquet")|
|fact_cost_to_serve|fnLoadParquet("fact_cost_to_serve.parquet")|
|meta_run|fnLoadParquet("meta_run.parquet")|
|qa_results|fnLoadParquet("qa_results.parquet")|

La forma completa de una consulta es:

~~~~powerquery
let
    Source = fnLoadParquet("dim_customer.parquet")
in
    Source
~~~~

Repetir cambiando archivo y nombre.

### 7.4 Tipos mínimos

Confirmar:

- claves terminadas en _key: Whole number;
- importes monetarios: Fixed decimal number cuando Power BI lo permita;
- ratios, cantidades, pesos, volumen y distancia: Decimal number;
- flags: True/False;
- IDs y categorías: Text;
- dim_date[date] y dim_date[month_start]: Date;
- meta_run[period_start], meta_run[period_end], meta_run[max_order_date] y meta_run[max_available_date]: Date;
- meta_run[validated_at]: Date/Time/Timezone o texto legible, sin reinterpretarlo como hora local de negocio.

No añadir joins, agrupaciones ni fórmulas de negocio en Power Query.

### 7.5 Aplicar y verificar

Close & Apply. En Data view verificar las filas de la sección 5.2.

### Evidencia a devolver

~~~~text
CHECKPOINT PBI-01
pDataRoot: C:\b2b-commercial-operational-system\data\marts
tables_loaded: 14
dim_customer: 150
dim_product: 30
dim_location: 151
dim_operational_site: 1
dim_vehicle: 7
dim_date: 365
fact_orders: 4000
fact_order_lines: 10000
fact_deliveries: 5000
fact_delivery_lines: 12483
fact_inventory: 10950
fact_cost_to_serve: 22165
meta_run: 1
qa_results: 184
refresh_errors: none
~~~~

### Gate

PASS sólo con las 14 tablas, todos los conteos exactos y cero errores.

## 8. PBI-02 — construir el modelo semántico

### 8.1 Reglas universales

Cada relación:

- cardinalidad: One to many, dimensión en el lado 1;
- cross-filter direction: Single;
- Assume referential integrity: no aplica al modo Import;
- ninguna relación many-to-many;
- ninguna relación bidireccional;
- ninguna relación entre facts;
- meta_run y qa_results permanecen desconectadas.

Power BI representa una relación activa con línea continua e inactiva con línea discontinua.

### 8.2 Relaciones no temporales activas

|Lado 1|Columna|Lado N|Columna|
|---|---|---|---|
|dim_customer|customer_key|fact_orders|customer_key|
|dim_customer|customer_key|fact_order_lines|customer_key|
|dim_customer|customer_key|fact_deliveries|customer_key|
|dim_customer|customer_key|fact_delivery_lines|customer_key|
|dim_customer|customer_key|fact_cost_to_serve|customer_key|
|dim_product|product_key|fact_order_lines|product_key|
|dim_product|product_key|fact_delivery_lines|product_key|
|dim_product|product_key|fact_inventory|product_key|
|dim_location|location_key|fact_orders|location_key|
|dim_location|location_key|fact_deliveries|location_key|
|dim_location|location_key|fact_delivery_lines|location_key|
|dim_location|location_key|fact_cost_to_serve|location_key|
|dim_operational_site|site_key|fact_deliveries|site_key|
|dim_operational_site|site_key|fact_delivery_lines|site_key|
|dim_operational_site|site_key|fact_inventory|site_key|
|dim_vehicle|vehicle_key|fact_deliveries|vehicle_key|
|dim_vehicle|vehicle_key|fact_delivery_lines|vehicle_key|
|dim_vehicle|vehicle_key|fact_cost_to_serve|vehicle_key|

### 8.3 Relaciones temporales

|Dimensión|Fact|Columna fact|Estado|
|---|---|---|---|
|dim_date[date_key]|fact_orders|order_date_key|Active|
|dim_date[date_key]|fact_orders|promised_date_key|Inactive|
|dim_date[date_key]|fact_orders|completion_date_key|Inactive|
|dim_date[date_key]|fact_order_lines|order_date_key|Active|
|dim_date[date_key]|fact_order_lines|promised_date_key|Inactive|
|dim_date[date_key]|fact_deliveries|delivery_date_key|Active|
|dim_date[date_key]|fact_deliveries|order_date_key|Inactive|
|dim_date[date_key]|fact_deliveries|dispatch_date_key|Inactive|
|dim_date[date_key]|fact_deliveries|promised_date_key|Inactive|
|dim_date[date_key]|fact_delivery_lines|order_date_key|Active|
|dim_date[date_key]|fact_delivery_lines|delivery_date_key|Inactive|
|dim_date[date_key]|fact_delivery_lines|promised_date_key|Inactive|
|dim_date[date_key]|fact_inventory|snapshot_date_key|Active|
|dim_date[date_key]|fact_cost_to_serve|order_date_key|Active|
|dim_date[date_key]|fact_cost_to_serve|activity_date_key|Inactive|
|dim_date[date_key]|fact_cost_to_serve|delivery_date_key|Inactive|

Total esperado:

- 34 relaciones;
- 24 activas;
- 10 inactivas;
- 0 many-to-many;
- 0 bidireccionales;
- 0 fact-to-fact.

### 8.4 Configurar dim_date

1. Marcar dim_date como Date table.
2. Elegir dim_date[date] como columna de fecha.
3. Sort dim_date[month_name] by dim_date[month_number].
4. Sort dim_date[year_month] by dim_date[month_start].
5. Usar dim_date[date] o dim_date[month_start] en slicers y ejes; no usar jerarquías automáticas.

### 8.5 Ocultar campos técnicos

Ocultar de Report view:

- surrogate keys de dimensiones;
- foreign keys y date keys de facts;
- scenario_id, dataset_build_id e is_synthetic en tablas de negocio;
- columnas técnicas usadas sólo para relaciones;
- columna auxiliar de la futura tabla _Measures.

Mantener visibles:

- customer_id, customer_name y customer_segment;
- sku_id, sku_name, product_family y unit;
- location_id, commune, region, country_code, latitude, longitude y data_class;
- site_id y site_type;
- vehicle_id y vehicle_type;
- order_id, order_line_id, delivery_id y cost_activity_id para trazabilidad;
- service_class, cost_type y otros campos de diagnóstico.

### Evidencia a devolver

~~~~text
CHECKPOINT PBI-02
relationships_total: 34
active: 24
inactive: 10
many_to_many: 0
bidirectional: 0
fact_to_fact: 0
date_tables: 1
dim_date_marked: yes
meta_run_disconnected: yes
qa_results_disconnected: yes
ambiguous_paths_warning: none
~~~~

Adjuntar una captura completa de Model view.

### Gate

PASS sólo si la matriz y los conteos coinciden exactamente.

## 9. PBI-03 — crear medidas

### 9.1 Tabla _Measures

1. Usar Enter data.
2. Crear una tabla llamada _Measures con una columna Holder y una fila Measures.
3. No crear relaciones.
4. Ocultar Holder.
5. Crear todas las medidas siguientes en _Measures.

Si Power BI usa punto y coma como separador regional, sustituir las comas de argumentos por punto y coma sin alterar las fórmulas.

### 9.2 Medidas contractuales

#### Economic

~~~~DAX
Net Sales =
SUM ( 'fact_orders'[recognized_net_sales] )
~~~~

~~~~DAX
Variable Product Cost =
SUM ( 'fact_orders'[variable_product_cost] )
~~~~

~~~~DAX
Contribution Margin =
[Net Sales] - [Variable Product Cost]
~~~~

~~~~DAX
CTS =
SUM ( 'fact_orders'[cts_amount] )
~~~~

~~~~DAX
MC_CTS =
IF (
    ISCROSSFILTERED ( 'dim_product'[product_key] ),
    BLANK (),
    [Contribution Margin] - [CTS]
)
~~~~

~~~~DAX
Average Order Value =
DIVIDE ( [Net Sales], [Orders] )
~~~~

Crear primero la medida `Orders`, ya que `Average Order Value` depende de ella.

#### Commercial

~~~~DAX
Orders =
DISTINCTCOUNT ( 'fact_orders'[order_id] )
~~~~

~~~~DAX
Customer Frequency =
DIVIDE ( [Orders], [Customers] )
~~~~

~~~~DAX
Customers =
DISTINCTCOUNT ( 'fact_orders'[customer_key] )
~~~~

#### Service

~~~~DAX
Eligible Orders =
CALCULATE (
    COUNTROWS ( 'fact_orders' ),
    'fact_orders'[eligible_order_flag] = TRUE (),
    USERELATIONSHIP ( 'dim_date'[date_key], 'fact_orders'[promised_date_key] )
)
~~~~

~~~~DAX
OTIF Orders =
CALCULATE (
    COUNTROWS ( 'fact_orders' ),
    'fact_orders'[eligible_order_flag] = TRUE (),
    'fact_orders'[order_otif_flag] = TRUE (),
    USERELATIONSHIP ( 'dim_date'[date_key], 'fact_orders'[promised_date_key] )
)
~~~~

~~~~DAX
OTIF =
DIVIDE ( [OTIF Orders], [Eligible Orders] )
~~~~

~~~~DAX
Fill Rate =
CALCULATE (
    DIVIDE (
        SUM ( 'fact_order_lines'[delivered_quantity] ),
        SUM ( 'fact_order_lines'[ordered_quantity] )
    ),
    USERELATIONSHIP (
        'dim_date'[date_key],
        'fact_order_lines'[promised_date_key]
    )
)
~~~~

~~~~DAX
Order-to-Delivery Lead Time =
CALCULATE (
    AVERAGE ( 'fact_orders'[lead_time_hours] ),
    'fact_orders'[in_full_flag] = TRUE (),
    USERELATIONSHIP ( 'dim_date'[date_key], 'fact_orders'[promised_date_key] )
)
~~~~

#### Inventory

~~~~DAX
Stockout Rate =
DIVIDE (
    CALCULATE (
        COUNTROWS ( 'fact_inventory' ),
        'fact_inventory'[is_stockout] = TRUE ()
    ),
    COUNTROWS ( 'fact_inventory' )
)
~~~~

~~~~DAX
Available Inventory EOP =
VAR LastVisibleDateKey = MAX ( 'dim_date'[date_key] )
RETURN
    CALCULATE (
        SUM ( 'fact_inventory'[available_quantity] ),
        'fact_inventory'[snapshot_date_key] = LastVisibleDateKey
    )
~~~~

#### Logistics

~~~~DAX
Delivery Distance =
SUM ( 'fact_deliveries'[distance_km] )
~~~~

~~~~DAX
Transport Cost =
CALCULATE (
    SUM ( 'fact_cost_to_serve'[cost_amount] ),
    'fact_cost_to_serve'[cost_type] = "transport"
)
~~~~

~~~~DAX
Vehicle Utilization =
AVERAGE ( 'fact_deliveries'[delivery_utilization] )
~~~~

### 9.3 Medidas auxiliares permitidas

Estas medidas no sustituyen las 19 medidas contractuales; habilitan visuales, trazabilidad y QA.

~~~~DAX
Net Sales by SKU =
SUM ( 'fact_delivery_lines'[recognized_net_sales] )
~~~~

~~~~DAX
Contribution Margin by SKU =
SUM ( 'fact_delivery_lines'[contribution_margin] )
~~~~

~~~~DAX
Ordered Quantity =
SUM ( 'fact_order_lines'[ordered_quantity] )
~~~~

~~~~DAX
Delivered Quantity =
SUM ( 'fact_order_lines'[delivered_quantity] )
~~~~

~~~~DAX
Orders by Promised Date =
CALCULATE (
    [Orders],
    USERELATIONSHIP ( 'dim_date'[date_key], 'fact_orders'[promised_date_key] )
)
~~~~

~~~~DAX
Available Inventory =
SUM ( 'fact_inventory'[available_quantity] )
~~~~

~~~~DAX
Safety Stock =
SUM ( 'fact_inventory'[safety_stock_quantity] )
~~~~

~~~~DAX
Reorder Point =
SUM ( 'fact_inventory'[reorder_point_quantity] )
~~~~

~~~~DAX
Weight Utilization =
AVERAGE ( 'fact_deliveries'[weight_utilization] )
~~~~

~~~~DAX
Volume Utilization =
AVERAGE ( 'fact_deliveries'[volume_utilization] )
~~~~

~~~~DAX
Order Fill Rate (Detail) =
DIVIDE (
    SUM ( 'fact_orders'[delivered_quantity] ),
    SUM ( 'fact_orders'[ordered_quantity] )
)
~~~~

~~~~DAX
Promised Date (Detail) =
VAR DateKey = SELECTEDVALUE ( 'fact_orders'[promised_date_key] )
RETURN
    LOOKUPVALUE ( 'dim_date'[date], 'dim_date'[date_key], DateKey )
~~~~

~~~~DAX
Completion Date (Detail) =
VAR DateKey = SELECTEDVALUE ( 'fact_orders'[completion_date_key] )
RETURN
    LOOKUPVALUE ( 'dim_date'[date], 'dim_date'[date_key], DateKey )
~~~~

~~~~DAX
QA Failed Gates =
CALCULATE (
    COUNTROWS ( 'qa_results' ),
    'qa_results'[status] <> "passed"
)
~~~~

~~~~DAX
QA Status =
IF ( [QA Failed Gates] = 0, "passed", "failed" )
~~~~

~~~~DAX
Dataset Build ID =
SELECTEDVALUE ( 'meta_run'[dataset_build_id] )
~~~~

~~~~DAX
Last Successful Execution =
SELECTEDVALUE ( 'meta_run'[validated_at] )
~~~~

~~~~DAX
Max Available Date =
SELECTEDVALUE ( 'meta_run'[max_available_date] )
~~~~

~~~~DAX
Customer Selection Valid =
INT ( HASONEVALUE ( 'dim_customer'[customer_key] ) )
~~~~

~~~~DAX
Customer 360 Message =
IF (
    [Customer Selection Valid] = 1,
    "Cliente: " & SELECTEDVALUE ( 'dim_customer'[customer_name] ),
    "Seleccione exactamente un cliente para habilitar Customer 360"
)
~~~~

### 9.4 Formato y display folders

|Folder|Medidas|
|---|---|
|Economic|Net Sales, Variable Product Cost, Contribution Margin, CTS, MC_CTS, Average Order Value, Net Sales by SKU, Contribution Margin by SKU|
|Commercial|Orders, Customer Frequency, Customers|
|Service|Eligible Orders, OTIF Orders, OTIF, Fill Rate, Order-to-Delivery Lead Time, Ordered Quantity, Delivered Quantity, Orders by Promised Date, Order Fill Rate (Detail), Promised Date (Detail), Completion Date (Detail)|
|Inventory|Stockout Rate, Available Inventory EOP, Available Inventory, Safety Stock, Reorder Point|
|Logistics|Delivery Distance, Transport Cost, Vehicle Utilization, Weight Utilization, Volume Utilization|
|Quality|QA Failed Gates, QA Status, Dataset Build ID, Last Successful Execution, Max Available Date, Customer Selection Valid, Customer 360 Message|

Formatos:

- CLP: Net Sales, Variable Product Cost, Contribution Margin, CTS, MC_CTS, Average Order Value, Net Sales by SKU, Contribution Margin by SKU y Transport Cost.
- Porcentaje 0.0%: OTIF, Fill Rate, Stockout Rate, Vehicle Utilization, Weight Utilization, Volume Utilization y Order Fill Rate (Detail).
- Entero: Orders, Customers, Eligible Orders, OTIF Orders y QA Failed Gates.
- Horas con dos decimales: Order-to-Delivery Lead Time.
- Kilómetros con tres decimales: Delivery Distance.
- Cantidades con tres decimales: inventario y cantidades.
- Fecha: Promised Date (Detail), Completion Date (Detail) y Max Available Date.

### 9.5 Validación de medidas

Crear temporalmente una tabla visual con el nombre de cada medida y su valor, o validar una por una mediante tarjetas.

Comprobar todos los valores de la sección 5.3.

Pruebas de filtro obligatorias:

1. Sin filtros, los 17 KPI y las 2 medidas de soporte reconcilian.
2. Seleccionar un SKU:
   - MC_CTS devuelve BLANK;
   - OTIF no cambia;
   - Fill Rate puede cambiar.
3. Net Sales by SKU, sin filtro de SKU, iguala Net Sales a 0,01 CLP.
4. Contribution Margin menos CTS iguala MC_CTS cuando no hay filtro de producto.
5. Available Inventory EOP para todo el período es 3.573, no la suma de los 365 snapshots.
6. QA Failed Gates es 0 y QA Status es passed.

### Evidencia a devolver

~~~~text
CHECKPOINT PBI-03
kpis_created: 17
support_measures_created: [cantidad]
net_sales: 14486600352.07
variable_product_cost: 8849398967.32
contribution_margin: 5637201384.75
cts: 2082958305.74
mc_cts: 3554243079.01
orders: 4000
aov: 3621650.0880175
otif: 0.7
fill_rate: 0.9257752874732879
lead_time_hours: 94.8175
stockout_rate: 0.02009132420091324
inventory_eop: 3573
customer_frequency: 26.666666666666668
delivery_distance: 269600.965
transport_cost: 1748790794.13
vehicle_utilization: 0.028494594187178403
customers: 150
sku_test_mc_cts: BLANK
sku_test_otif: unchanged
net_sales_sku_reconciliation: passed
qa_status: passed
errors: none
~~~~

### Gate

PASS sólo si las 17 medidas existen, los controles están dentro de tolerancia y pasan las seis pruebas de filtro.

## 10. PBI-04 — construir exactamente cuatro páginas Core

### 10.1 Elementos comunes

Todas las páginas deben mostrar:

- Dataset Build ID;
- Last Successful Execution;
- Max Available Date;
- QA Status.

Filtros globales permitidos:

- período desde dim_date[date];
- segmento desde dim_customer[customer_segment];
- región desde dim_location[region].

Usar View > Sync slicers sólo en páginas donde el filtro tenga significado. Un filtro regional o de cliente puede afectar métricas de servicio, pero no debe presentarse como filtro de inventario si no existe esa relación.

Diseño:

- fondo claro;
- texto oscuro;
- grillas discretas;
- jerarquía hero metrics, tendencia, diagnóstico, detalle;
- barras desde cero;
- títulos que indiquen métrica, unidad y contexto;
- sin colores de meta, porque no existen metas empresariales;
- sólo QA puede usar semáforo;
- no depender sólo del color.

### 10.2 Página 1 — Executive

Pregunta:

¿Cómo evoluciona el resultado económico y qué guardrails requieren atención?

Hero cards:

1. MC_CTS
2. Net Sales
3. CTS
4. OTIF
5. Fill Rate
6. Orders
7. Customers

Visuales:

1. Economía mensual:
   - tipo: line chart;
   - eje: dim_date[month_start];
   - valores: Net Sales y MC_CTS;
   - mostrar 12 meses.
2. Servicio mensual:
   - tipo: line chart;
   - eje: dim_date[month_start];
   - valores: OTIF y Fill Rate;
   - subtítulo: fecha prometida y denominadores elegibles.
3. Clientes por MC_CTS:
   - tipo: horizontal bar;
   - categoría: dim_customer[customer_name];
   - valor: MC_CTS;
   - orden descendente;
   - eje con cero visible;
   - permitir scroll para top y bottom.

### 10.3 Página 2 — Customer 360

Pregunta:

¿Qué valor, servicio y costo explican la situación de un cliente?

1. Añadir slicer dim_customer[customer_name].
2. Activar Single select.
3. Añadir una card con Customer 360 Message.
4. Para todos los demás visuales, aplicar visual-level filter Customer Selection Valid = 1.

Hero cards:

- Net Sales;
- Contribution Margin;
- CTS;
- MC_CTS;
- Orders;
- Customer Frequency;
- OTIF;
- Fill Rate;
- Order-to-Delivery Lead Time.

Visuales:

1. Economía del cliente:
   - line chart;
   - eje: dim_date[month_start];
   - valores: Net Sales, Contribution Margin, CTS y MC_CTS.
2. Mix SKU:
   - horizontal bar;
   - categoría: dim_product[sku_name];
   - valor: Net Sales by SKU;
   - no usar MC_CTS por SKU.
3. Servicio por pedido:
   - table;
   - fact_orders[order_id];
   - Promised Date (Detail);
   - Completion Date (Detail);
   - fact_orders[service_class];
   - Order Fill Rate (Detail);
   - CTS;
   - MC_CTS.

### 10.4 Página 3 — Service & Inventory

Pregunta:

¿Dónde se originan incumplimientos y riesgo de inventario?

Filtros locales:

- dim_operational_site[site_id];
- dim_product[sku_name].

El subtítulo de OTIF debe indicar:

OTIF oficial a grain pedido; el filtro SKU no aplica.

Hero cards:

- OTIF;
- Fill Rate;
- Order-to-Delivery Lead Time;
- Stockout Rate;
- Available Inventory EOP.

Visuales:

1. Servicio mensual:
   - line chart;
   - eje: dim_date[month_start];
   - valores: OTIF y Fill Rate;
   - tooltips: Eligible Orders y OTIF Orders.
2. Fill Rate por SKU:
   - horizontal bar;
   - categoría: dim_product[sku_name];
   - valor: Fill Rate;
   - tooltip: Ordered Quantity;
   - orden ascendente para mostrar riesgo primero.
3. Stockout SKU × mes:
   - matrix con formato condicional;
   - filas: dim_product[sku_name];
   - columnas: dim_date[year_month];
   - valores: Stockout Rate.
4. Inventario seleccionado:
   - line chart;
   - eje: dim_date[date];
   - valores: Available Inventory, Safety Stock y Reorder Point;
   - requiere SKU y sitio seleccionados para una lectura útil.
5. Clases de servicio:
   - 100% stacked bar;
   - leyenda: fact_orders[service_class];
   - valor: Orders by Promised Date.

### 10.5 Página 4 — Profitability & Geography

Pregunta:

¿Qué clientes y zonas combinan valor, costo y distancia de manera desfavorable?

Filtros:

- dim_date[date];
- dim_customer[customer_segment];
- dim_location[region];
- dim_location[commune].

Hero cards:

- MC_CTS;
- CTS;
- Transport Cost;
- Delivery Distance;
- Vehicle Utilization.

Visuales:

1. Mapa de clientes:
   - latitude: dim_location[latitude];
   - longitude: dim_location[longitude];
   - size: Net Sales;
   - details o tooltip: dim_customer[customer_name];
   - tooltip: MC_CTS, commune y data_class;
   - aclarar procedencia sintética.
2. Ventas vs CTS:
   - scatter a grain cliente;
   - X: Net Sales;
   - Y: CTS;
   - details: dim_customer[customer_name];
   - legend: dim_customer[customer_segment];
   - mostrar sólo con al menos 20 clientes visibles;
   - con menos de 8, reemplazar por tabla o barras.
3. MC_CTS por cliente:
   - horizontal bar;
   - categoría: dim_customer[customer_name];
   - valor: MC_CTS;
   - cero visible.
4. Rentabilidad y logística:
   - table;
   - customer_name, commune, region;
   - Net Sales, CTS, MC_CTS;
   - Delivery Distance, Transport Cost, OTIF.

No usar rojo/verde para el signo de MC_CTS. Usar dos tonos accesibles, etiquetas y línea de cero.

### Evidencia a devolver

~~~~text
CHECKPOINT PBI-04
pages_total: 4
page_1: Executive
page_2: Customer 360
page_3: Service & Inventory
page_4: Profitability & Geography
metadata_strip_all_pages: yes
customer_360_requires_one_customer: yes
sku_filter_mc_cts_blank: yes
sku_filter_otif_unchanged: yes
visual_errors: none
~~~~

Adjuntar una captura completa de cada página.

### Gate

PASS sólo si existen exactamente las cuatro páginas y cada una responde su pregunta contractual.

## 11. PBI-05 — aceptación interactiva final

### 11.1 Modelo y refresh

- b2b_v1.pbix abre sin error.
- pDataRoot puede cambiarse a otra reconstrucción local de marts.
- Refresh completa.
- 34 relaciones correctas.
- Cero M:M, bidireccionales o rutas ambiguas.
- Una sola dim_date.
- Conteos de hechos reconciliados.
- IDs de negocio disponibles para drill-through.
- Claves técnicas ocultas.

### 11.2 Medidas

- 17 KPI, 2 medidas de soporte y 20 auxiliares documentados.
- Moneda dentro de 0,01 CLP.
- Cantidades dentro de 0,001.
- Ratios dentro de 1e-9.
- Denominador cero produce BLANK.
- Net Sales by SKU reconcilia.
- CTS detallado reconcilia con fact_orders.
- MC_CTS cumple fórmula y queda BLANK bajo SKU.
- OTIF usa fecha prometida.
- Fill Rate es ratio de sumas.
- EOP usa última fecha visible.

### 11.3 Experiencia

- Exactamente cuatro páginas.
- Executive funciona sin interacción.
- Customer 360 exige un cliente.
- Filtros coherentes.
- Alcance SKU señalado.
- Mapa con coordenadas válidas y procedencia.
- Trazabilidad customer → order → delivery → CTS → MC_CTS.
- Build, freshness y QA en todas las páginas.
- Cero visuales decorativos.

### Evidencia a devolver

~~~~text
CHECKPOINT PBI-05
refresh: passed
model_gate: passed
measure_gate: passed
experience_gate: passed
pbix_path: C:\b2b-commercial-operational-system\powerbi\b2b_v1.pbix
remaining_caveats: none
~~~~

### Gate

Este checkpoint puede cerrar el incremento Power BI, pero no aprueba automáticamente V1.0. Codex debe revisar la evidencia y el usuario debe aprobar el hito de forma explícita.

## 12. Diagnóstico rápido

### No aparece Parquet

- Usar Get data > Parquet o la función fnLoadParquet.
- Confirmar que pDataRoot no termina en un nombre de archivo.
- Confirmar que el archivo existe en data\marts.

### Error de privacidad o credenciales

- La fuente es un archivo local.
- Usar autenticación local de Windows cuando corresponda.
- No convertir la ruta en una URL.

### Power BI creó relaciones incorrectas

- Eliminar todas las automáticas.
- Recrear sólo la matriz PBI-02.
- No resolver el problema con Both o M:M.

### OTIF cambia con SKU

- Verificar que fact_orders no tenga product_key.
- Verificar que no exista relación entre facts.
- Verificar que no exista filtro bidireccional.

### MC_CTS no queda BLANK con SKU

- Confirmar el uso de ISCROSSFILTERED sobre dim_product[product_key].
- Confirmar que el visual usa MC_CTS y no fact_orders[mc_cts_amount] directamente.

### Fill Rate no coincide

- Usar suma entregada dividida por suma pedida.
- No promediar ratios por línea.
- Confirmar USERELATIONSHIP con promised_date_key.

### EOP es demasiado alto

- El visual probablemente suma snapshots.
- Usar Available Inventory EOP, no fact_inventory[available_quantity] directamente en una tarjeta.

### Valores económicos se duplican

- No unir facts.
- No usar columnas de fact_delivery_lines para el KPI ejecutivo.
- Net Sales, CTS y MC_CTS oficiales provienen de fact_orders.

## 13. Referencias normativas

- Contrato KPI y Power BI: docs/KPI-POWERBI-SPEC.md
- Contrato de datos: docs/DATA-CONTRACT.md
- Contrato operativo: AGENTS.md
- Controles Python: data/manifest/kpi_controls.json
- QA de marts: data/manifest/marts_quality_report.json
- Manifiesto: data/manifest/run_manifest.json

Documentación oficial Microsoft:

- Parámetros de Power Query:
  https://learn.microsoft.com/en-us/power-query/power-query-query-parameters
- Conector Parquet:
  https://learn.microsoft.com/es-es/power-query/connectors/parquet
- Relaciones del modelo:
  https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand
- Relaciones activas e inactivas:
  https://learn.microsoft.com/es-es/power-bi/guidance/relationships-active-inactive
- Tabla de fechas:
  https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-date-tables
- Esquema estrella:
  https://learn.microsoft.com/en-ie/power-bi/guidance/star-schema

## 14. Registro de actualización interactiva

|Fecha|Versión|Checkpoint|Estado|Cambio|
|---|---|---|---|---|
|2026-08-14|0.1|Inicial|active_manual_build|Se crea guía integral para carga, modelo, medidas, cuatro páginas y aceptación interactiva.|
|2026-08-14|0.2|PBI-00|IN_PROGRESS|Captura validada en opciones globales: Auto date/time para archivos nuevos desactivado y ValueFilterBehavior Independiente conservado.|
|2026-08-14|0.3|PBI-00|PASSED|Archivo b2b_v1.pbix guardado. El usuario confirma que, en las opciones del archivo actual, Auto date/time y las tres opciones de Relaciones están desactivadas.|
|2026-08-14|0.4|PBI-01|IN_PROGRESS|El usuario confirma la creación del parámetro pDataRoot con la ruta contractual de data/marts.|
|2026-08-14|0.5|PBI-01|IN_PROGRESS|El usuario confirma la creación de fnLoadParquet como función auxiliar sin carga.|
|2026-08-14|0.6|PBI-01|IN_PROGRESS|dim_customer carga correctamente desde fnLoadParquet y reconcilia las 150 filas contractuales sin errores.|
|2026-08-14|0.7|PBI-01|IN_PROGRESS|dim_product carga correctamente desde fnLoadParquet y reconcilia las 30 filas contractuales. Avance: 2 de 14 tablas.|
|2026-08-14|0.8|PBI-01|IN_PROGRESS|dim_location carga correctamente desde fnLoadParquet y reconcilia las 151 filas contractuales. Avance: 3 de 14 tablas.|
|2026-08-14|0.9|PBI-01|IN_PROGRESS|dim_operational_site carga correctamente desde fnLoadParquet y reconcilia la única fila contractual. Avance: 4 de 14 tablas.|
|2026-08-14|1.0|PBI-01|IN_PROGRESS|dim_vehicle carga correctamente desde fnLoadParquet y reconcilia las 7 filas contractuales. Avance: 5 de 14 tablas.|
|2026-08-14|1.1|PBI-01|IN_PROGRESS|dim_date carga correctamente desde fnLoadParquet y reconcilia las 365 filas contractuales. Avance: 6 de 14 tablas; dimensiones completas.|
|2026-08-14|1.2|PBI-01|IN_PROGRESS|fact_orders carga correctamente desde fnLoadParquet y reconcilia las 4.000 filas contractuales. Avance: 7 de 14 tablas.|
|2026-08-14|1.3|PBI-01|IN_PROGRESS|fact_order_lines carga correctamente desde fnLoadParquet y reconcilia las 10.000 filas contractuales. Avance: 8 de 14 tablas.|
|2026-08-14|1.4|PBI-01|IN_PROGRESS|fact_deliveries carga correctamente desde fnLoadParquet y reconcilia las 5.000 filas contractuales. Avance: 9 de 14 tablas.|
|2026-08-14|1.5|PBI-01|IN_PROGRESS|fact_delivery_lines carga correctamente desde fnLoadParquet y reconcilia las 12.483 filas contractuales. Avance: 10 de 14 tablas.|
|2026-08-14|1.6|PBI-01|IN_PROGRESS|fact_inventory carga correctamente desde fnLoadParquet y reconcilia las 10.950 filas contractuales. Avance: 11 de 14 tablas.|
|2026-08-14|1.7|PBI-01|IN_PROGRESS|fact_cost_to_serve carga correctamente desde fnLoadParquet y reconcilia las 22.165 filas contractuales. Avance: 12 de 14 tablas; hechos completos.|
|2026-08-14|1.8|PBI-01|IN_PROGRESS|meta_run carga correctamente desde fnLoadParquet y reconcilia la única fila contractual. Avance: 13 de 14 tablas.|
|2026-08-14|1.9|PBI-01|IN_PROGRESS|qa_results carga correctamente desde fnLoadParquet y reconcilia las 184 filas contractuales. Las 14 consultas fueron validadas; falta aplicar la carga al modelo.|
|2026-08-14|2.0|PBI-01|IN_PROGRESS|El usuario confirma que Cerrar y aplicar completó la carga de las 14 tablas sin errores; falta guardar el PBIX.|
|2026-08-14|2.1|PBI-01|PASSED|Se verifica b2b_v1.pbix guardado con 2.588.451 bytes después de aplicar las 14 tablas sin errores y reconciliar sus conteos.|
|2026-08-14|2.2|PBI-02|IN_PROGRESS|El usuario confirma que la Vista Modelo abre con 0 relaciones visibles; se inicia la creación manual de la matriz contractual.|
|2026-08-14|2.3|PBI-02|IN_PROGRESS|Captura validada de la relación 01: dim_customer[customer_key] → fact_orders[customer_key], activa, 1:*, filtro único. Avance: 1 de 34.|
|2026-08-14|2.4|PBI-02|IN_PROGRESS|El usuario confirma la relación 02: dim_customer[customer_key] → fact_order_lines[customer_key]. Avance: 2 de 34.|
|2026-08-14|2.5|PBI-02|IN_PROGRESS|El usuario confirma la relación 03: dim_customer[customer_key] → fact_deliveries[customer_key]. Avance: 3 de 34.|
|2026-08-14|2.6|PBI-02|IN_PROGRESS|El usuario confirma la relación 04: dim_customer[customer_key] → fact_delivery_lines[customer_key]. Avance: 4 de 34.|
|2026-08-14|2.7|PBI-02|IN_PROGRESS|El usuario confirma la relación 05: dim_customer[customer_key] → fact_cost_to_serve[customer_key]. Avance: 5 de 34.|
|2026-08-14|2.8|PBI-02|IN_PROGRESS|El usuario confirma la relación 06: dim_product[product_key] → fact_order_lines[product_key]. Avance: 6 de 34.|
|2026-08-14|2.9|PBI-02|IN_PROGRESS|Captura validada de la relación 07: dim_product[product_key] → fact_delivery_lines[product_key], activa, 1:* y filtro único. Avance: 7 de 34.|
|2026-08-14|2.10|PBI-02|IN_PROGRESS|El usuario confirma la relación 08: dim_product[product_key] → fact_inventory[product_key]. Avance: 8 de 34.|
|2026-08-14|2.11|PBI-02|IN_PROGRESS|El usuario confirma la relación 09: dim_location[location_key] → fact_orders[location_key]. Avance: 9 de 34.|
|2026-08-14|2.12|PBI-02|IN_PROGRESS|El usuario confirma la relación 10: dim_location[location_key] → fact_deliveries[location_key]. Avance: 10 de 34.|
|2026-08-14|2.13|PBI-02|IN_PROGRESS|El usuario confirma la relación 11: dim_location[location_key] → fact_delivery_lines[location_key]. Avance: 11 de 34.|
|2026-08-14|2.14|PBI-02|IN_PROGRESS|El usuario confirma la relación 12: dim_location[location_key] → fact_cost_to_serve[location_key]. Avance: 12 de 34.|
|2026-08-15|2.15|PBI-02|IN_PROGRESS|El usuario confirma la relación 13: dim_operational_site[site_key] → fact_deliveries[site_key]. Avance: 13 de 34.|
|2026-08-15|2.16|PBI-02|IN_PROGRESS|El usuario confirma la relación 14: dim_operational_site[site_key] → fact_delivery_lines[site_key]. Avance: 14 de 34.|
|2026-08-15|2.17|PBI-02|IN_PROGRESS|El usuario confirma la relación 15: dim_operational_site[site_key] → fact_inventory[site_key]. Avance: 15 de 34.|
|2026-08-15|2.18|PBI-02|IN_PROGRESS|El usuario confirma la relación 16: dim_vehicle[vehicle_key] → fact_deliveries[vehicle_key]. Avance: 16 de 34.|
|2026-08-15|2.19|PBI-02|IN_PROGRESS|El usuario confirma la relación 17: dim_vehicle[vehicle_key] → fact_delivery_lines[vehicle_key]. Avance: 17 de 34.|
|2026-08-15|2.20|PBI-02|IN_PROGRESS|El usuario confirma la relación 18: dim_vehicle[vehicle_key] → fact_cost_to_serve[vehicle_key]. Avance: 18 de 34; bloque no temporal completado.|
|2026-08-15|2.21|PBI-02|IN_PROGRESS|El usuario confirma la relación 19: dim_date[date_key] → fact_orders[order_date_key], activa. Avance: 19 de 34.|
|2026-08-15|2.22|PBI-02|IN_PROGRESS|El usuario confirma la relación 20: dim_date[date_key] → fact_orders[promised_date_key], inactiva. Avance: 20 de 34.|
|2026-08-15|2.23|PBI-02|IN_PROGRESS|El usuario confirma la relación 21: dim_date[date_key] → fact_orders[completion_date_key], inactiva. Avance: 21 de 34.|
|2026-08-15|2.24|PBI-02|IN_PROGRESS|El usuario confirma la relación 22: dim_date[date_key] → fact_order_lines[order_date_key], activa. Avance: 22 de 34.|
|2026-08-15|2.25|PBI-02|IN_PROGRESS|El usuario confirma la relación 23: dim_date[date_key] → fact_order_lines[promised_date_key], inactiva. Avance: 23 de 34.|
|2026-08-15|2.26|PBI-02|IN_PROGRESS|El usuario confirma la relación 24: dim_date[date_key] → fact_deliveries[delivery_date_key], activa. Avance: 24 de 34.|
|2026-08-15|2.27|PBI-02|IN_PROGRESS|El usuario confirma la relación 25: dim_date[date_key] → fact_deliveries[order_date_key], inactiva. Avance: 25 de 34.|
|2026-08-15|2.28|PBI-02|IN_PROGRESS|El usuario confirma la relación 26: dim_date[date_key] → fact_deliveries[dispatch_date_key], inactiva. Avance: 26 de 34.|
|2026-08-15|2.29|PBI-02|IN_PROGRESS|El usuario confirma la relación 27: dim_date[date_key] → fact_deliveries[promised_date_key], inactiva. Avance: 27 de 34.|
|2026-08-15|2.30|PBI-02|IN_PROGRESS|El usuario confirma la relación 28: dim_date[date_key] → fact_delivery_lines[order_date_key], activa. Avance: 28 de 34.|
|2026-08-15|2.31|PBI-02|IN_PROGRESS|El usuario confirma la relación 29: dim_date[date_key] → fact_delivery_lines[delivery_date_key], inactiva. Avance: 29 de 34.|
|2026-08-15|2.32|PBI-02|IN_PROGRESS|El usuario confirma la relación 30: dim_date[date_key] → fact_delivery_lines[promised_date_key], inactiva. Avance: 30 de 34.|
|2026-08-15|2.33|PBI-02|IN_PROGRESS|El usuario confirma la relación 31: dim_date[date_key] → fact_inventory[snapshot_date_key], activa. Avance: 31 de 34.|
|2026-08-15|2.34|PBI-02|IN_PROGRESS|El usuario confirma la relación 32: dim_date[date_key] → fact_cost_to_serve[order_date_key], activa. Avance: 32 de 34.|
|2026-08-15|2.35|PBI-02|IN_PROGRESS|El usuario confirma la relación 33: dim_date[date_key] → fact_cost_to_serve[activity_date_key], inactiva. Avance: 33 de 34.|
|2026-08-15|2.36|PBI-02|IN_PROGRESS|El usuario confirma la relación 34: dim_date[date_key] → fact_cost_to_serve[delivery_date_key], inactiva. Matriz completa; pendiente de validación final.|
|2026-08-15|2.37|PBI-02|PASSED|Validación final confirmada en Power BI: 34 relaciones, 24 activas, 10 inactivas; meta_run y qa_results desconectadas. PBIX guardado.|
|2026-08-15|2.38|PBI-03|IN_PROGRESS|El usuario crea _Measures, sin relaciones y con Holder oculto; se inicia la creación de medidas DAX contractuales.|
|2026-08-15|2.39|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual 01: Net Sales.|
|2026-08-15|2.40|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual 02: Variable Product Cost.|
|2026-08-15|2.41|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual 03: Contribution Margin.|
|2026-08-15|2.42|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual 04: CTS.|
|2026-08-15|2.43|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual 05: MC_CTS.|
|2026-08-15|2.44|PBI-03|IN_PROGRESS|El usuario confirma las medidas contractuales Orders y Average Order Value; se documenta la dependencia de creación entre ambas.|
|2026-08-15|2.45|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Customers.|
|2026-08-15|2.46|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Customer Frequency.|
|2026-08-15|2.47|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Eligible Orders.|
|2026-08-15|2.48|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual OTIF Orders.|
|2026-08-15|2.49|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual OTIF.|
|2026-08-15|2.50|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Fill Rate.|
|2026-08-15|2.51|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Order-to-Delivery Lead Time.|
|2026-08-15|2.52|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Stockout Rate.|
|2026-08-15|2.53|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Available Inventory EOP.|
|2026-08-15|2.54|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Delivery Distance.|
|2026-08-15|2.55|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Transport Cost.|
|2026-08-15|2.56|PBI-03|IN_PROGRESS|El usuario confirma la creación de la medida contractual Vehicle Utilization; las 19 medidas contractuales están creadas. Se corrige la referencia de 17 a 19 medidas en la guía.|
|2026-08-15|2.57|PBI-03|IN_PROGRESS|Validación visual confirmada: 19 medidas, Holder oculto, sin errores DAX y PBIX guardado. Se inicia el bloque de medidas auxiliares.|
|2026-08-15|2.58|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 01: Net Sales by SKU.|
|2026-08-15|2.59|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 02: Contribution Margin by SKU.|
|2026-08-15|2.60|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 03: Ordered Quantity.|
|2026-08-15|2.61|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 04: Delivered Quantity.|
|2026-08-15|2.62|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 05: Orders by Promised Date.|
|2026-08-15|2.63|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 06: Available Inventory.|
|2026-08-15|2.64|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 07: Safety Stock.|
|2026-08-15|2.65|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 08: Reorder Point.|
|2026-08-15|2.66|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 09: Weight Utilization.|
|2026-08-15|2.67|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 10: Volume Utilization.|
|2026-08-15|2.68|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 11: Order Fill Rate (Detail).|
|2026-08-15|2.69|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 12: Promised Date (Detail).|
|2026-08-15|2.70|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 13: Completion Date (Detail).|
|2026-08-15|2.71|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 14: QA Failed Gates.|
|2026-08-15|2.72|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 15: QA Status.|
|2026-08-15|2.73|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 16: Dataset Build ID.|
|2026-08-15|2.74|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 17: Last Successful Execution.|
|2026-08-15|2.75|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 18: Max Available Date.|
|2026-08-15|2.76|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 19: Customer Selection Valid.|
|2026-08-15|2.77|PBI-03|IN_PROGRESS|El usuario confirma la medida auxiliar 20: Customer 360 Message. Se completan 20 medidas auxiliares y 39 medidas totales en _Measures.|
|2026-08-15|2.78|PBI-03|IN_PROGRESS|Validación visual confirmada: 39 medidas totales (19 contractuales y 20 auxiliares), Holder oculto, sin errores DAX y PBIX guardado.|
|2026-08-15|2.79|PBI-03|IN_PROGRESS|Prueba económica sin filtros validada en tabla: Net Sales, Variable Product Cost, Contribution Margin, CTS, MC_CTS y Average Order Value reconcilian con el contrato.|
|2026-08-15|2.80|PBI-03|IN_PROGRESS|Prueba comercial y de servicio sin filtros validada: Orders, Customers, Customer Frequency, Eligible Orders, OTIF Orders, OTIF, Fill Rate y Order-to-Delivery Lead Time reconcilian visualmente con el contrato.|
|2026-08-15|2.81|PBI-03|IN_PROGRESS|Prueba de inventario y logística sin filtros validada: Stockout Rate, Available Inventory EOP, Delivery Distance, Transport Cost y Vehicle Utilization reconcilian visualmente con el contrato.|
|2026-08-15|2.82|PBI-03|IN_PROGRESS|Reconciliación sin filtro validada: Net Sales by SKU equivale a Net Sales dentro de la tolerancia contractual.|
|2026-08-15|2.83|PBI-03|IN_PROGRESS|Se corrige la instrucción del segmentador de SKU: el campo disponible en dim_product es sku_id.|
|2026-08-15|2.84|PBI-03|IN_PROGRESS|Prueba de SKU validada: MC_CTS devuelve BLANK; OTIF permanece en 0,70; Fill Rate cambia con el SKU seleccionado.|
|2026-08-15|2.85|PBI-03|PASSED|Validación final confirmada: QA Failed Gates=0 y QA Status=passed, además de las reconciliaciones sin filtro y con SKU. Las 39 medidas están creadas, sin errores DAX.|
|2026-08-15|2.86|PBI-04|IN_PROGRESS|Se elimina la página temporal de QA y se crea la primera página Core: Executive.|
|2026-08-15|2.87|PBI-04|IN_PROGRESS|El usuario confirma el título de la página Executive; se inicia la construcción de indicadores principales y visuales.|
|2026-08-15|2.88|PBI-04|IN_PROGRESS|El usuario confirma la franja Executive con siete hero metrics: MC_CTS, Net Sales, CTS, OTIF, Fill Rate, Orders y Customers.|
|2026-08-15|2.89|PBI-04|IN_PROGRESS|El usuario confirma los tres visuales Executive: economía mensual, servicio mensual y clientes por MC_CTS.|
|2026-08-15|2.90|PBI-04|IN_PROGRESS|El usuario confirma la franja de metadata y QA de Executive; QA Status=passed y PBIX guardado.|
|2026-08-15|2.91|PBI-04|IN_PROGRESS|El usuario confirma exactamente cuatro páginas Core: Executive, Customer 360, Service & Inventory y Profitability & Geography.|
|2026-08-15|2.92|PBI-04|IN_PROGRESS|Captura validada de Customer 360: título creado, selector customer_name con selección única y Customer 360 Message responde al cliente seleccionado.|
|2026-08-15|2.93|PBI-04|IN_PROGRESS|El usuario confirma los visuales Customer 360 de economía mensual y mix SKU.|
|2026-08-15|2.94|PBI-04|IN_PROGRESS|Se corrigen Promised Date (Detail) y Completion Date (Detail): reemplazan DATE() sobre clave por LOOKUPVALUE hacia dim_date[date], tras error de tipo en tabla de detalle.|
|2026-08-15|2.95|PBI-04|IN_PROGRESS|El usuario confirma las fechas de detalle corregidas y la tabla Servicio por pedido sin errores.|
|2026-08-15|2.96|PBI-04|IN_PROGRESS|Customer 360 completada: tabla Servicio por pedido, metadata, QA Status=passed y PBIX guardado. El ajuste de tamaños, tipografía y alineación se difiere a la pasada visual final común a las cuatro páginas.|
|2026-08-15|2.97|PBI-04|IN_PROGRESS|Service & Inventory: título, nota sobre el grain de OTIF y segmentadores independientes site_id / sku_name creados sin errores. Se evita el DataViewMappingError al no mezclar ambos campos en un mismo segmentador.|
|2026-08-15|2.98|PBI-04|IN_PROGRESS|Service & Inventory: creada la franja de cinco indicadores (OTIF, Fill Rate, Order-to-Delivery Lead Time, Stockout Rate y Available Inventory EOP), sin errores y con PBIX guardado.|
|2026-08-15|2.99|PBI-04|IN_PROGRESS|Service & Inventory: gráfico de cumplimiento mensual validado. OTIF y Fill Rate son las dos únicas líneas; Eligible Orders y OTIF Orders quedaron correctamente en tooltip.|
|2026-08-15|3.00|PBI-04|IN_PROGRESS|Service & Inventory: completados sin errores el gráfico Fill Rate por SKU (orden ascendente y tooltip de cantidades) y la matriz Stockout Rate por SKU y mes; PBIX guardado.|
|2026-08-15|3.01|PBI-04|IN_PROGRESS|Service & Inventory funcionalmente completada: gráfico de inventario y umbrales (tres líneas), mix mensual de pedidos por clase de servicio corregido a columnas apiladas 100 %, metadata, QA Status=passed y PBIX guardado.|
|2026-08-15|3.02|PBI-04|IN_PROGRESS|Profitability & Geography: título, aviso de datos sintéticos y cuatro filtros independientes creados. El filtro de periodo usa selección de rango; los otros filtran customer_segment, region y commune.|
|2026-08-15|3.03|PBI-04|IN_PROGRESS|Profitability & Geography: creada la franja Rentabilidad y costo logístico con MC_CTS, CTS, Transport Cost, Delivery Distance y Vehicle Utilization; sin errores y PBIX guardado.|
|2026-08-15|3.04|PBI-04|IN_PROGRESS|Profitability & Geography: creados Clientes por MC_CTS y Ventas netas versus CTS por cliente. Evidencia visual valida que las tarjetas, barras y dispersión cambian correctamente entre los segmentos enterprise y mid_market.|
|2026-08-15|3.05|PBI-04|IN_PROGRESS|Profitability & Geography: mapa ArcGIS validado como invitado con puntos visibles y tooltip de commune, region, data_class=synthetic y MC_CTS. Se crea además la tabla Rentabilidad y servicio por cliente, sin errores; PBIX guardado.|
|2026-08-15|3.06|PBI-04|IN_PROGRESS|Profitability & Geography completada: metadata creada, QA Status=passed y PBIX guardado. Las cuatro páginas Core están funcionalmente construidas; queda la pasada visual final de tamaños, alineación, tipografía y revisión de aceptación.|
|2026-08-15|3.07|PBI-04|IN_PROGRESS|Inicia pasada visual final. Revisión de Executive evidencia jerarquía y distribución correctas; se identifican recortes de texto en valores KPI y metadata como ajustes de legibilidad pendientes.|
|2026-08-16|3.08|PBI-04|IN_PROGRESS|Executive validada visualmente: KPIs legibles tras ajustar valores/etiquetas, metadata en cuadrícula de dos columnas sin recortes relevantes, y layout final ordenado.|
|2026-08-16|3.09|PBI-04|IN_PROGRESS|Customer 360: el selector customer_name vuelve a estar visible y se valida selección única; la selección de Cliente Sintético 002 actualiza correctamente el mensaje y los visuales.|
|2026-08-16|3.10|PBI-04|IN_PROGRESS|Customer 360: se corrige Economía mensual del cliente, retirando customer_name del eje y month_start de la leyenda; month_start queda en eje X y las cuatro métricas económicas son series temporales.|
|2026-08-16|3.11|PBI-04|IN_PROGRESS|Customer 360 validada visualmente: selector y mensaje dinámico visibles, nueve KPI en cuadrícula 5+4 sin recortes, economía temporal corregida, mix SKU, tabla de servicio y metadata en dos columnas legibles.|
|2026-08-16|3.12|PBI-04|IN_PROGRESS|Service & Inventory revisada visualmente: layout de filtros, KPI, cumplimiento, Fill Rate, matriz de stockout, inventario, mix y metadata es correcto. Queda sólo un ajuste menor de tamaño para evitar el recorte del Dataset Build ID.|
|2026-08-16|3.13|PBI-04|IN_PROGRESS|Profitability & Geography revisada visualmente: filtros, hero, barras, dispersión, mapa ArcGIS, tabla y metadata están presentes y sin error. Quedan ajustes de layout: ampliar tabla y mover metadata a una fila inferior de ancho completo para evitar recortes.|
|2026-08-16|3.14|RELEASE|IN_PROGRESS|Se sincroniza el estado real como RELEASE_CANDIDATE: PBI-03 queda PASSED con 39 medidas; PBI-04 conserva ajustes visuales menores y PBI-05 requiere refresh, recorrido interactivo, drill-through, exportación PBIP/PBIR y evidencia final.|
|2026-08-16|3.15|RELEASE|PASSED|El usuario acepta explícitamente el archivo PBIX construido manualmente en Power BI Desktop, cierra PBI-04/PBI-05 y autoriza declarar y publicar v1.0.0.|
