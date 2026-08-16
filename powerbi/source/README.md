# Power BI versionable source

This directory is the source-control companion of `../b2b_v1.pbix`.

## Current status

| Artifact | Status | Authority |
|---|---|---|
| `../b2b_v1.pbix` | accepted for V1.0 | authoritative executable Power BI artifact |
| `TMDLScripts/measures.tmdl` | present | reviewable mirror of the 39 DAX measures |
| `model-contract.json` | present | reviewable contract for tables, relationships, pages and gates |
| PBIP/TMDL semantic-model export | optional post-V1 | must be produced by Power BI Desktop |
| PBIR report export | optional post-V1 | must be produced and verified by Power BI Desktop |

This folder intentionally does **not** contain a fabricated `.pbip` or PBIR
definition. Microsoft supports PBIX-to-PBIP conversion only through Power BI
Desktop's **File > Save As** operation. The generated files must therefore be
exported from the verified PBIX and reviewed before becoming authoritative. The
user accepted the manually authored PBIX as the V1.0 artifact on 2026-08-16.

## Optional post-V1 migration checkpoint

1. Open `powerbi/b2b_v1.pbix` in Power BI Desktop.
2. Preserve the accepted V1.0 PBIX before converting it.
3. Enable the Power BI Project, TMDL semantic model, and enhanced report format
   preview features if the installed Desktop version still requires them.
4. Use **File > Save As** and select **Power BI Project (.pbip)**.
5. Save under `powerbi/source/export/b2b_v1/` using TMDL for the semantic model
   and PBIR for the report.
6. Close and reopen the generated `.pbip`.
7. Refresh from `data/marts` and confirm:
   - 14 loaded tables;
   - 34 relationships: 24 active and 10 inactive;
   - 39 measures;
   - exactly four Core pages;
   - QA Failed Gates = 0 and QA Status = passed;
   - control totals reconcile with `data/manifest/kpi_controls.json`.
8. Compare the exported measures with `TMDLScripts/measures.tmdl` and resolve
   only explained differences.
9. Commit the PBIP/TMDL/PBIR text sources. Do not commit local cache files under
   `.pbi/`.

The interactive checklist is maintained in
`../../docs/chats_instruction/POWER-BI-INTERACTIVE-GUIDE.md`.
