---
doc_id: "MVP-D04"
title: "Codex Operating Contract — V1.0 Core"
version: "0.1"
status: "approved"
type: "operating_contract"
created: "2026-08-13"
updated: "2026-08-13"
depends_on:
  - "MVP-D00"
  - "MVP-D01"
  - "MVP-D02"
  - "MVP-D03"
---

# Codex Operating Contract — V1.0 Core

## 1. Propósito

Este archivo instruye a cualquier agente que trabaje en este workspace. Su objetivo es convertir los contratos aprobados en una implementación local, determinista, comprobable y limitada a V1.0 Core.

La ruta obligatoria es:

```text
Contracts + Configuration
→ Synthetic Generator
→ Synthetic CSV
→ Validation / QC
→ Validated Parquet
→ Analytical Marts
→ Star Schema
→ Power BI
→ V1.0 Acceptance
```

No implementar un ERP, CRM u optimizador. No utilizar datos operacionales reales.

## 2. Autoridad

Ante una contradicción, aplicar este orden:

1. instrucción explícita vigente del usuario;
2. `docs/PROJECT-CONTROL.md` — alcance, gates y política de release;
3. `docs/MVP-SPEC.md` — comportamiento observable;
4. `docs/DATA-CONTRACT.md` — datasets, campos, grains, claves y calidad;
5. `docs/KPI-POWERBI-SPEC.md` — marts, métricas y dashboard;
6. este `AGENTS.md` — procedimiento operativo;
7. documentos históricos o de investigación.

Los documentos D00–D03 aprobados son fuente de verdad. Este archivo no modifica su semántica.

Si código, pruebas y contrato discrepan:

```text
1. detener la promoción del artefacto afectado
2. reportar la divergencia y su impacto
3. preservar el contrato aprobado
4. corregir la implementación o solicitar un cambio contractual explícito
5. nunca ejecutar una migración semántica silenciosa
```

Cambiar un grain, PK, FK, campo, fórmula, restricción o rol de fecha exige aprobación del contrato correspondiente.

## 3. Estado y prohibición de Git

```yaml
target_release: "V1.0"
release_status: "PRE_RELEASE"
implementation_mode: "local_codex_step_by_step"
git_policy: "DISABLED_UNTIL_V1_0_APPROVAL"
```

Hasta que el usuario apruebe la consolidación V1.0:

- no ejecutar comandos Git;
- no crear repositorios, commits, ramas ni tags;
- no utilizar Git para restaurar, comparar o borrar archivos;
- no asumir que V1.0 está aprobada por el solo hecho de pasar pruebas.

Incluso después de aprobar V1.0, comenzar a usar Git requiere una instrucción explícita adicional del usuario.

## 4. Forma de trabajo

Antes de modificar:

1. leer este archivo y los contratos que gobiernan la tarea;
2. inspeccionar el estado real de los archivos afectados;
3. declarar el artefacto principal de la iteración y sus criterios de cierre;
4. preservar cambios del usuario que no pertenezcan a la tarea.

Durante la implementación:

- trabajar con un artefacto principal por iteración;
- mantener cambios pequeños, trazables y verificables;
- preferir Python, pandas, pytest, CSV y Parquet;
- no introducir servicios cloud, secretos o acceso de red obligatorio;
- no añadir frameworks opcionales sin necesidad demostrable;
- no crear documentación sin una función verificable;
- no ocultar reglas estructurales o económicas dentro de Power BI.

Antes de cerrar una iteración:

1. ejecutar las pruebas aplicables;
2. validar outputs y reconciliaciones;
3. informar archivos modificados, resultados y limitaciones;
4. mantener el artefacto contractual en `in_review` hasta aprobación explícita;
5. no avanzar al siguiente gate documental si el usuario aún no aprobó el actual.

## 5. Estructura objetivo

La fundación ejecutable posterior a la aprobación de D04 deberá converger a:

```text
config/
  scenario_base.yaml
data/
  synthetic/
  validated/
  marts/
  manifest/
schemas/
src/
  synthetic/
  validation/
  marts/
  pipeline.py
tests/
  fixtures/
    golden/
    invalid/
powerbi/
  b2b_v1.pbix
docs/
AGENTS.md
requirements.txt
```

Los módulos podrán subdividirse sin alterar la interfaz contractual ni duplicar conceptos.

No escribir outputs temporales o caches dentro de carpetas contractuales. Los outputs fallidos no deben reemplazar una corrida válida anterior.

## 6. Interfaz contractual de ejecución

La fundación deberá implementar y documentar estos comandos desde la raíz del workspace:

```powershell
python -m pip install -r requirements.txt
python -m src.pipeline --config config/scenario_base.yaml
python -m pytest -q
```

El segundo comando es la ejecución end-to-end oficial de `B2B-V1-BASE` y debe:

```text
load configuration
→ generate synthetic datasets
→ validate all quality gates
→ publish validated tables
→ build analytical marts
→ calculate control KPIs
→ emit manifest and QA report
```

Contrato de salida:

- exit code `0`: toda la ejecución y los gates obligatorios terminaron correctamente;
- exit code distinto de `0`: existe error o gate fallido;
- una falla debe dejar diagnóstico sanitizado y no promover datos parciales;
- la ruta de configuración debe ser explícita, sin depender del directorio personal;
- la ejecución no debe requerir red ni credenciales.

Los comandos constituyen la interfaz contractual aprobada; no se afirmará que existen hasta implementarlos y probarlos en la siguiente fase.

## 7. Configuración base

`config/scenario_base.yaml` será la configuración canónica de aceptación:

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

Todo valor adicional debe ser explícito, serializable y participar en `config_sha256` cuando afecte resultados.

## 8. Datos, publicación y trazabilidad

Fuentes oficiales por etapa:

|Etapa|Ruta|Formato|Regla|
|---|---|---|---|
|Generación|`data/synthetic/<dataset>.csv`|CSV|salida fuente sintética|
|Validación|`data/validated/<dataset>.parquet`|Parquet|sólo datos que pasaron gates|
|Analítica|`data/marts/<table>.parquet`|Parquet|dimensiones, hechos y tablas técnicas|
|Ejecución|`data/manifest/run_manifest.json`|JSON|identidad, conteos, hashes y estado|
|Calidad|`data/manifest/quality_report.json`|JSON|resultado de cada gate|

Cada dataset contractual preservará `scenario_id`, `dataset_build_id` e `is_synthetic` según D02. Nunca presentar datos sintéticos como hechos empresariales reales.

El `dataset_build_id` debe depender de configuración, semilla y versiones, no del timestamp. Dos builds equivalentes deben producir los mismos IDs, filas ordenadas, valores y checksums tabulares.

El manifiesto registrará como mínimo:

```text
scenario_id
seed
generator_version
schema_version
config_sha256
dataset_build_id
execution_id and executed_at
input and output paths
rows read, written and rejected by dataset
rejection reasons
artifact SHA-256
quality-gate results
duration and status
sanitized error, if any
```

Los timestamps de ejecución pueden variar; los archivos tabulares y sus controles deterministas no.

## 9. Reglas semánticas no negociables

- Todo dato operacional es sintético; una referencia pública debe clasificarse explícitamente.
- Los datasets, tipos, PK, FK, nulabilidad y grains son los definidos en D02.
- Un pedido puede tener múltiples entregas y una entrega pertenece a un pedido en V1.0.
- La cantidad entregada acumulada por línea nunca excede la cantidad pedida.
- Ventas y costo variable se reconocen sobre cantidades entregadas.
- OTIF se calcula a grain pedido elegible; Fill Rate es ratio de sumas.
- CTS suma cada actividad una sola vez y debe reconciliar con el pedido.
- `MC_CTS = Net Sales - Variable Product Cost - CTS`; no es margen neto.
- MC_CTS y CTS no se atribuyen a SKU en V1.0; bajo filtro de producto, MC_CTS devuelve `BLANK()` en Power BI.
- Inventario es snapshot diario y semi-aditivo en el tiempo.
- El modelo analítico conserva seis dimensiones y seis hechos de D03; no crear mega-tabla.
- Las relaciones Power BI son dimensión `1:N`, filtro simple, sin many-to-many ni fact-to-fact.
- Existe una sola `dim_date`; los roles activos e inactivos siguen D03.
- Power BI consume marts validados y no reimplementa validación ni transformaciones estructurales.

## 10. Estrategia de pruebas

La suite debe cubrir, como mínimo:

|Nivel|Evidencia obligatoria|
|---|---|
|Unitario|IDs, fechas, cantidades, economía y helpers deterministas|
|Contrato|schema, tipos, nulabilidad, PK, FK, dominios y grains de D02|
|Negativo|fixtures inválidos rechazados por el gate correcto|
|Golden|OTIF, Fill Rate, CTS y MC_CTS con resultado conocido|
|Integración|pedido reconstruible con líneas, entregas y costos sin duplicación|
|Reproducibilidad|dos builds equivalentes con los mismos checksums tabulares|
|Marts|conteos, grains y reconciliación entre detalle y `fact_orders`|
|Power BI|medidas reconciliadas con Python y refresh desde marts|

No debilitar una validación para hacer pasar un test. Corregir el dato, la implementación o, con aprobación, el contrato.

Tolerancias oficiales para reconciliación:

```text
currency: 0.01 CLP
quantity: 0.001 units
ratio absolute tolerance: 1e-9
zero denominator: BLANK, never infinity or an invented zero
```

## 11. Gates de entrega

Una etapa sólo puede alimentar a la siguiente si cumple:

```text
Generation Gate
  deterministic outputs + base scenario coverage

Validation Gate
  schema + PK/FK + ranges + time + economics + provenance

Marts Gate
  declared grains + no join amplification + reconciled totals

Power BI Gate
  valid star model + 17 metrics + exactly 4 Core pages + refresh

V1.0 Gate
  D00–D04 approved + clean end-to-end run + complete Definition of Done
```

Una corrida fallida puede conservar artefactos diagnósticos, pero no puede identificarse como build válido ni ser consumida por Power BI.

## 12. Definition of Done por incremento

Un incremento de implementación está terminado cuando:

- el comportamiento solicitado existe en archivos del workspace;
- las pruebas nuevas y las de regresión aplicables pasan;
- los outputs respetan D02 y D03;
- errores y datos sintéticos quedan claramente identificados;
- no quedan decisiones críticas ocultas ni `TBD` introducidos por el cambio;
- el resultado, comandos ejecutados y evidencia se presentan al usuario;
- el siguiente paso no se inicia cuando requiere una aprobación pendiente.

La Definition of Done del release completo es la de D00. Ningún agente puede promover `release_status` a `V1.0` sin aprobación explícita del usuario.

## 13. Seguridad y límites

- No incorporar secretos, tokens, credenciales ni datos personales reales.
- No registrar paths personales, variables sensibles o payloads completos en errores.
- No depender de recursos remotos para ejecutar el Core.
- No borrar ni sobrescribir material del usuario sin comprobar alcance y necesidad.
- No añadir ERPNext, CRM, n8n, PostgreSQL, dbt, forecasting, routing ni machine learning al Core.
- DuckDB y notebooks son opcionales y no pueden convertirse en dependencias ocultas.

## 14. Estado

```yaml
PROJECT_PROGRESS:
  target_release: "V1.0"
  release_status: "PRE_RELEASE"
  stage: "IMPLEMENTATION"
  current_work_item: "MVP-I01"
  name: "EXECUTABLE FOUNDATION"
  status: "NOT_STARTED"
  completed:
    - "MVP-D00"
    - "MVP-D01"
    - "MVP-D02"
    - "MVP-D03"
    - "MVP-D04"
  next: "SYNTHETIC GENERATOR"
  blockers: []
```

## 15. Registro de cambios

|Fecha|Versión documento|Estado|Cambio|
|---|---|---|---|
|2026-08-13|0.1|approved|Se aprueba el contrato operativo para traducir D00–D03 a una implementación reproducible, validada y sin Git hasta V1.0.|
