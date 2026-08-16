from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json

from src.pipeline import (
    EXIT_CONFIGURATION_ERROR,
    EXIT_OK,
    EXIT_VALIDATION_FAILED,
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


def test_end_to_end_command_orchestrates_and_promotes(
    capsys, monkeypatch, tmp_path
) -> None:
    calls: list[str] = []
    generated = GeneratedSyntheticData(
        dataset_build_id="BLD-TEST",
        tables={"customers": [1, 2, 3]},
    )

    def publish_generated(data, output):
        calls.append("generation")
        output.mkdir(parents=True)
        (output / "customers.csv").write_text("customer_id\n1\n", encoding="utf-8")
        return {"customers": "ABC"}

    outcome = SimpleNamespace(
        dataset_build_id="BLD-TEST",
        results=[SimpleNamespace(status="passed")],
        passed=True,
        status="passed",
    )

    def validate(config, *, input_dir, validated_dir, manifest_dir, schema_path):
        calls.append("validation")
        assert (input_dir / "customers.csv").is_file()
        validated_dir.mkdir(parents=True)
        (validated_dir / "customers.parquet").write_bytes(b"PAR1")
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "run_manifest.json").write_text(
            json.dumps({"dataset_build_id": "BLD-TEST", "paths": {}}),
            encoding="utf-8",
        )
        return SimpleNamespace(
            execution_id="EXE-TEST",
            outcome=outcome,
            published=True,
        )

    mart_gate = SimpleNamespace(status="passed")

    def build_marts(config, *, validated_dir, marts_dir, manifest_dir):
        calls.append("marts")
        assert (validated_dir / "customers.parquet").is_file()
        marts_dir.mkdir(parents=True)
        (marts_dir / "dim_customer.parquet").write_bytes(b"PAR1")
        return SimpleNamespace(
            dataset_build_id="BLD-TEST",
            marts_execution_id="MRT-TEST",
            mart_hashes={"dim_customer": "DEF"},
            published=True,
            results=[mart_gate],
            status="passed",
        )

    monkeypatch.setattr("src.pipeline.generate_synthetic_data", lambda config: generated)
    monkeypatch.setattr("src.pipeline.publish_synthetic_csvs", publish_generated)
    monkeypatch.setattr("src.pipeline.validate_and_publish", validate)
    monkeypatch.setattr("src.pipeline.build_and_publish_marts", build_marts)

    synthetic = tmp_path / "synthetic"
    validated = tmp_path / "validated"
    marts = tmp_path / "marts"
    manifest = tmp_path / "manifest"
    exit_code = main(
        [
            "--config", str(BASE_CONFIG),
            "--output-dir", str(synthetic),
            "--validated-dir", str(validated),
            "--marts-dir", str(marts),
            "--manifest-dir", str(manifest),
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    final_manifest = json.loads(
        (manifest / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert exit_code == EXIT_OK
    assert calls == ["generation", "validation", "marts"]
    assert result["status"] == "passed"
    assert result["generation"]["files"] == 1
    assert final_manifest["pipeline"]["status"] == "passed"
    assert final_manifest["pipeline"]["stages"][-2:] == [
        "kpi_controls", "manifest"
    ]
    assert (synthetic / "customers.csv").is_file()
    assert (validated / "customers.parquet").is_file()
    assert (marts / "dim_customer.parquet").is_file()
    assert captured.err == ""


def test_end_to_end_failure_preserves_previous_valid_outputs(
    capsys, monkeypatch, tmp_path
) -> None:
    generated = GeneratedSyntheticData(
        dataset_build_id="BLD-TEST",
        tables={"customers": [1]},
    )
    final_dirs = [
        tmp_path / "synthetic",
        tmp_path / "validated",
        tmp_path / "marts",
        tmp_path / "manifest",
    ]
    for directory in final_dirs:
        directory.mkdir()
        (directory / "sentinel.txt").write_text("previous-valid", encoding="utf-8")

    def publish_generated(data, output):
        output.mkdir(parents=True)
        return {"customers": "ABC"}

    failed_gate = SimpleNamespace(status="failed")
    failed_outcome = SimpleNamespace(
        dataset_build_id="BLD-TEST",
        results=[failed_gate],
        passed=False,
        status="failed",
    )

    def validate(config, *, input_dir, validated_dir, manifest_dir, schema_path):
        manifest_dir.mkdir(parents=True)
        return SimpleNamespace(
            execution_id="EXE-FAILED",
            outcome=failed_outcome,
            published=False,
        )

    monkeypatch.setattr("src.pipeline.generate_synthetic_data", lambda config: generated)
    monkeypatch.setattr("src.pipeline.publish_synthetic_csvs", publish_generated)
    monkeypatch.setattr("src.pipeline.validate_and_publish", validate)

    exit_code = main(
        [
            "--config", str(BASE_CONFIG),
            "--output-dir", str(final_dirs[0]),
            "--validated-dir", str(final_dirs[1]),
            "--marts-dir", str(final_dirs[2]),
            "--manifest-dir", str(final_dirs[3]),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_VALIDATION_FAILED
    assert '"stage": "validation"' in captured.err
    assert all(
        (directory / "sentinel.txt").read_text(encoding="utf-8")
        == "previous-valid"
        for directory in final_dirs
    )


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
