from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.pipeline import (
    EXIT_CONFIGURATION_ERROR,
    EXIT_OK,
    EXIT_PIPELINE_NOT_IMPLEMENTED,
    main,
)
from src.synthetic.generator import GeneratedSyntheticData


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = ROOT / "config" / "scenario_base.yaml"


def test_config_preflight_succeeds(capsys) -> None:
    exit_code = main(["--config", str(BASE_CONFIG), "--check-config"])

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert '"scenario_id": "B2B-V1-BASE"' in captured.out
    assert '"status": "config_valid"' in captured.out
    assert captured.err == ""


def test_missing_config_fails_without_traceback(capsys) -> None:
    missing = ROOT / "tests" / "fixtures" / "invalid" / "missing.yaml"
    assert not missing.exists()
    exit_code = main(["--config", str(missing), "--check-config"])

    captured = capsys.readouterr()
    assert exit_code == EXIT_CONFIGURATION_ERROR
    assert "configuration_error:" in captured.err
    assert "Traceback" not in captured.err


def test_end_to_end_command_does_not_claim_false_success(capsys) -> None:
    exit_code = main(["--config", str(BASE_CONFIG)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_PIPELINE_NOT_IMPLEMENTED
    assert "Power BI is pending" in captured.err


def test_generate_only_publishes_via_pipeline(capsys, monkeypatch) -> None:
    generated = GeneratedSyntheticData(
        dataset_build_id="BLD-TEST",
        tables={"customers": [1, 2, 3]},
    )
    monkeypatch.setattr("src.pipeline.generate_synthetic_data", lambda config: generated)
    monkeypatch.setattr(
        "src.pipeline.publish_synthetic_csvs",
        lambda data, output: {"customers": "ABC"},
    )

    exit_code = main(
        [
            "--config", str(BASE_CONFIG), "--generate-only", "--output-dir",
            "unused-test-output",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert '"dataset_build_id": "BLD-TEST"' in captured.out
    assert '"status": "synthetic_published"' in captured.out


def test_validate_only_reports_success(capsys, monkeypatch) -> None:
    outcome = SimpleNamespace(
        dataset_build_id="BLD-TEST",
        results=[],
        passed=True,
        status="passed",
    )
    run = SimpleNamespace(
        execution_id="EXE-TEST",
        outcome=outcome,
        published=True,
    )
    monkeypatch.setattr("src.pipeline.validate_and_publish", lambda *args, **kwargs: run)

    exit_code = main(["--config", str(BASE_CONFIG), "--validate-only"])

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert '"published": true' in captured.out
    assert '"status": "passed"' in captured.out


def test_build_marts_only_reports_success(capsys, monkeypatch) -> None:
    gate = SimpleNamespace(status="passed")
    run = SimpleNamespace(
        dataset_build_id="BLD-TEST",
        marts_execution_id="MRT-TEST",
        mart_hashes={"dim_date": "ABC"},
        published=True,
        results=[gate],
        status="passed",
    )
    monkeypatch.setattr("src.pipeline.build_and_publish_marts", lambda *args, **kwargs: run)

    exit_code = main(["--config", str(BASE_CONFIG), "--build-marts-only"])

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert '"marts_execution_id": "MRT-TEST"' in captured.out
    assert '"published": true' in captured.out
