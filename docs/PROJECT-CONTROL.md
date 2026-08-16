---
doc_id: "MVP-D00"
title: "Project Control — V1.0"
version: "0.3"
status: "approved"
type: "governance"
created: "2026-08-13"
updated: "2026-08-16"
---

# Project Control — V1.0

## 1. Proyecto

**Sistema Comercial–Operacional B2B — objetivo V1.0**

Objetivo: construir con Codex, localmente y paso a paso, un piloto reproducible con **datos sintéticos/hipotéticos**, finalizarlo en un modelo analítico y dashboard Power BI, y consolidarlo como la primera versión funcional **V1.0**.

La prioridad es:

```text
V1.0 funcional
> documentación extensa
```

El estado anterior de los documentos se considera **material de preparación**. Desde esta revisión, los documentos contractuales serán corregidos y aprobados secuencialmente mientras Codex implementa el proyecto.

### 1.1 Estado de release

```yaml
target_release: "V1.0"
release_status: "RELEASE_CANDIDATE"
document_version: "0.2"
execution_environment: "local"
implementation_mode: "codex_step_by_step"
git_policy: "DISABLED_UNTIL_V1_0_APPROVAL"
```

`V1.0` se declarará únicamente cuando se cumpla la Definition of Done de este documento. La existencia de avances parciales no promueve automáticamente el release.

### 1.2 Precedencia documental

Ante una contradicción, se aplicará el siguiente orden:

1. instrucción explícita vigente del usuario;
2. `PROJECT-CONTROL.md`;
3. `MVP-SPEC.md`;
4. `DATA-CONTRACT.md`;
5. `KPI-POWERBI-SPEC.md`;
6. `AGENTS.md`, una vez creado;
7. documentos históricos, guías, planes base e investigaciones.

Los documentos históricos orientan el roadmap, pero no amplían silenciosamente el alcance de V1.0.

---

## 2. Principio rector

El sistema debe permitir recorrer:

```text
Cliente
→ Pedido
→ SKU
→ Inventario
→ Despacho
→ Entrega
→ Servicio
→ Cost-to-Serve
→ MC_CTS
→ Decisión
```

Power BI será la capa de consumo.

La lógica crítica deberá permanecer fuera del dashboard siempre que sea razonable:

```text
datos
→ validación
→ transformación
→ modelo analítico
→ Power BI
```

---

## 3. Sitio operacional de referencia

```yaml
site_id: "SOR-01"
type: "operational_logistics_node"
address_reference: "Las Esteras Sur, Quilicura, Región Metropolitana, Chile"
coordinates: "TBD"
```

SOR-01 representa hipotéticamente:

- recepción;

- almacenamiento;

- inventario;

- picking;

- consolidación;

- despacho;

- distribución B2B.


No se utilizarán nombres corporativos dentro del MVP.

---

## 4. Naturaleza de los datos

Todo dato operacional del piloto será:

```text
SYNTHETIC
```

salvo información geográfica o contextual explícitamente identificada como referencia pública.

Identificadores sugeridos:

```text
CUS-SYN-001
SKU-SYN-001
ORD-SYN-000001
VEH-SYN-01
```

Nunca presentar datos sintéticos como observaciones reales.

---

## 5. Escenario mínimo objetivo

Parámetros iniciales ajustables:

```yaml
customers: 150
skus: 30
operational_sites: 1
vehicles: 6
history_months: 12
orders_approx: 4000
order_lines_approx: 10000
```

El generador deberá producir suficiente variabilidad para observar:

- clientes de distinto valor;

- pedidos grandes y pequeños;

- mix de SKU;

- stockouts;

- entregas tardías;

- entregas incompletas;

- diferentes zonas geográficas;

- diferencias de CTS;

- clientes rentables y poco rentables.


---

## 6. Alcance V1.0 Core

### Obligatorio

```text
Customers
Products / SKU
Orders
Order Lines
Inventory
Deliveries
Vehicles
Locations
Cost-to-Serve
```

Analítica mínima:

```text
Net Sales
Contribution Margin
CTS
MC_CTS
OTIF
Fill Rate
Lead Time
Inventory
Stockout
Orders
Customer Frequency
Distance / Delivery Cost
```

Power BI mínimo:

```text
Executive
Customer 360
Service & Inventory
Profitability & Geography
```

---

## 7. Fuera de V1.0 Core

No son requisitos para considerar terminado el primer piloto:

```text
ERPNext
Twenty CRM
n8n
StatsForecast
SciPy / Statsmodels
OSRM
VROOM
OR-Tools
PostgreSQL
dbt
machine learning
real messaging
real customer data
```

Son extensiones posteriores a V1.0 Core.

No deben retrasar la primera versión funcional de Power BI.

---

## 8. Arquitectura mínima

```text
Synthetic Generator
        ↓
Synthetic Data
        ↓
Validation / QC
        ↓
Analytical Tables
        ↓
Star Schema
        ↓
Power BI
        ↓
Decision
```

Implementación local preferida para V1.0:

```text
Python + pandas
CSV/Parquet
pytest
DuckDB opcional
Power BI Desktop
```

La ejecución inicial será manual mediante comandos Python documentados. n8n, MCP y otros orquestadores no forman parte del Core V1.0.

---

## 9. Documentación contractual mínima

Cinco documentos forman el contrato de construcción:

|Orden|Documento|Función|
|---|---|---|
|D00|`PROJECT-CONTROL.md`|alcance, estado y reglas|
|D01|`MVP-SPEC.md`|comportamiento esperado del piloto|
|D02|`DATA-CONTRACT.md`|datos, entidades, campos, relaciones y QC|
|D03|`KPI-POWERBI-SPEC.md`|KPIs, modelo estrella y dashboard|
|D04|`AGENTS.md`|instrucciones operativas para Codex|

Los demás documentos existentes se clasifican como **referencia histórica o roadmap**. No prevalecen sobre D00–D04 y no obligan a implementar funciones fuera del Core.

No crear documentación adicional sin una función verificable.

---

## 10. Artefactos ejecutables previstos

Después de D00–D03:

```text
data/
├── synthetic/
├── validated/
└── marts/

src/
├── synthetic/
├── validation/
└── marts/

schemas/

tests/

config/

powerbi/
└── b2b_v1.pbix
```

Los nombres podrán ser refinados durante implementación.

Cada ejecución completa deberá producir un manifiesto con semilla, versiones, conteos, resultados de calidad y checksums de artefactos.

---

## 11. Reglas de calidad

Como mínimo:

```text
PK no nula
PK única
FK válida
cantidad >= 0
precio >= 0
costo >= 0
delivery_date >= order_date
shipped_quantity <= ordered_quantity
SKU existente
Customer existente
is_synthetic = true
```

Las reglas exactas se especificarán en `DATA-CONTRACT.md`.

---

## 12. Criterio económico

La métrica rectora será:

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

CTS deberá poder explicarse mediante componentes identificables, aunque el primer modelo utilice parámetros sintéticos simplificados.

---

## 13. Criterio Power BI

Power BI debe consumir hechos y dimensiones con granularidad explícita.

No construir una única mega-tabla que mezcle:

```text
pedido
inventario
entrega
cliente
ruta
costo
```

si éstos representan granularidades distintas.

La especificación definitiva se establecerá en `KPI-POWERBI-SPEC.md`.

---

## 14. Clasificación mínima

Usar únicamente cuando aporte claridad:

```text
FACT
DESIGN
ASSUMPTION
SYNTHETIC
TBD
```

No crear un sistema documental más complejo para estas categorías durante V1.0 Core.

---

## 15. Flujo de trabajo con Codex

Para cada documento:

```text
analizar
→ crear o corregir
→ revisar
→ corregir
→ presentar al usuario
→ aprobar explícitamente
→ siguiente
```

Codex podrá:

- leer el repositorio;

- detectar inconsistencias;

- generar código;

- crear tests;

- consolidar documentación;

- refactorizar;

- optimizar pipelines.

Se trabajará con **un artefacto principal por iteración**. Un documento o contrato no se marcará `approved` sin confirmación explícita del usuario.

### 15.1 Política de Git posterior a la aprobación

El usuario aprobó la consolidación para Git y la publicación el 2026-08-16:

```text
usar ramas y commits pequeños y verificables
publicar contratos sanitizados y evidencia reproducible
no depender de Git para la reproducibilidad de datos
reservar el tag y GitHub Release v1.0.0 hasta cerrar todos los gates
```

La trazabilidad técnica se conserva mediante:

- versión y estado dentro de cada contrato;
- registro de cambios documental;
- manifiestos de ejecución;
- hashes SHA-256 de artefactos consolidados;
- aprobación explícita de cada gate.

La autorización para Git no promueve por sí sola el estado a `V1.0`. Mientras
PBI-04 y PBI-05 conserven evidencia pendiente, el estado es
`RELEASE_CANDIDATE`.


---

## 16. Definition of Done de V1.0

V1.0 estará terminada cuando:

1. los datos sintéticos puedan regenerarse reproduciblemente;

2. las relaciones PK/FK sean válidas;

3. los principales KPIs puedan recalcularse;

4. Power BI tenga un modelo estrella funcional;

5. pueda seleccionarse un cliente y rastrear:


```text
Customer
→ Orders
→ Delivery
→ Service
→ CTS
→ MC_CTS
```

6. exista al menos una vista geográfica;

7. los datos sintéticos estén inequívocamente identificados;

8. otra IA pueda comprender el repositorio leyendo `AGENTS.md` y los cuatro contratos públicos D00–D03.

9. la misma configuración, semilla y versión del generador produzcan los mismos registros y totales de control;

10. todas las pruebas de esquema, PK, FK, rangos, temporalidad y reglas económicas pasen;

11. existan fixtures inválidos que demuestren que los validadores detectan errores;

12. los KPIs se recalculen fuera de Power BI y se reconcilien con el dashboard;

13. CTS pueda descomponerse en componentes identificables sin doble conteo;

14. una ejecución limpia produzca datos sintéticos, datos validados, marts, KPIs, manifiesto y reporte de calidad;

15. `PROJECT-CONTROL.md`, `MVP-SPEC.md`, `DATA-CONTRACT.md`, `KPI-POWERBI-SPEC.md` y `AGENTS.md` estén aprobados;

16. no existan decisiones críticas marcadas como `TBD`;

17. `powerbi/b2b_v1.pbix` abra, actualice sus datos y muestre los totales de control esperados;

18. todos los datos operacionales estén identificados inequívocamente como sintéticos;

19. el pipeline pueda ejecutarse sin datos reales, secretos, servicios cloud ni acceso de red obligatorio.


---

## 17. Control de avance

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

## 18. Regla de versión

El objetivo de release es:

```text
V1.0
```

Mientras no se cumpla la Definition of Done, el estado será:

```text
RELEASE_CANDIDATE
```

Las versiones de documentos, contrato de datos, esquema, generador y release son independientes y deben registrarse por separado.

No se crearán versiones globales intermedias por cada incremento funcional. La promoción a V1.0 exige aprobación explícita del usuario.

---

## 19. Registro de cambios

|Fecha|Versión documento|Estado|Cambio|
|---|---|---|---|
|2026-08-13|0.1|draft|Borrador previo al trabajo con Codex.|
|2026-08-13|0.2|approved|Se establece y aprueba el objetivo V1.0, la precedencia contractual, la construcción con Codex, el Core acotado y la política sin Git.|
|2026-08-16|0.3|approved|Se sincroniza el estado RELEASE_CANDIDATE, la autorización de Git y el cierre técnico, manteniendo pendientes los gates finales de Power BI y el release v1.0.0.|
