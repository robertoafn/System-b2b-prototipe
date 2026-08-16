from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "powerbi" / "source"


def test_powerbi_model_contract_counts_and_rules() -> None:
    contract = json.loads(
        (SOURCE / "model-contract.json").read_text(encoding="utf-8")
    )
    relationships = contract["relationships"]

    assert contract["release_status"] == "V1.0"
    assert len(relationships) == 34
    assert sum(item["active"] for item in relationships) == 24
    assert sum(not item["active"] for item in relationships) == 10
    assert contract["relationship_rules"] == {
        "cardinality": "one-to-many",
        "filter_direction": "single",
        "many_to_many": 0,
        "bidirectional": 0,
        "fact_to_fact": 0,
        "active": 24,
        "inactive": 10,
        "total": 34,
    }
    assert contract["pages"] == [
        "Executive",
        "Customer 360",
        "Service & Inventory",
        "Profitability & Geography",
    ]
    assert set(contract["release_gates"].values()) == {"PASSED"}


def test_powerbi_tmdl_contains_39_unique_measures() -> None:
    tmdl = (SOURCE / "TMDLScripts" / "measures.tmdl").read_text(
        encoding="utf-8"
    )
    measures = re.findall(r"^\s+measure\s+(?:'([^']+)'|([^\s=]+))\s*=", tmdl, re.M)
    names = [quoted or unquoted for quoted, unquoted in measures]

    assert tmdl.startswith("createOrReplace\n")
    assert len(names) == 39
    assert len(set(names)) == 39
    assert {"Net Sales", "MC_CTS", "OTIF", "Fill Rate", "QA Status"} <= set(
        names
    )
