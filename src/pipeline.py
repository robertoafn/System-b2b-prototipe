"""Command-line entry point for the V1.0 Core pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from src.config import ConfigurationError, load_scenario_config
from src.marts.builder import build_and_publish_marts
from src.synthetic.generator import generate_synthetic_data, publish_synthetic_csvs
from src.validation.publisher import validate_and_publish


EXIT_OK = 0
EXIT_CONFIGURATION_ERROR = 2
EXIT_PIPELINE_NOT_IMPLEMENTED = 3
EXIT_GENERATION_ERROR = 4
EXIT_VALIDATION_FAILED = 5
EXIT_VALIDATION_ERROR = 6
EXIT_MARTS_FAILED = 7
EXIT_MARTS_ERROR = 8


def _sanitized_error(exc: Exception) -> str:
    message = " ".join(str(exc).splitlines())
    replacements = (
        (str(Path.cwd().resolve()), "<workspace>"),
        (str(Path.home().resolve()), "<home>"),
    )
    for raw_path, label in replacements:
        message = message.replace(raw_path, label)
    return f"{type(exc).__name__}: {message[:500]}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the synthetic B2B V1.0 analytical dataset."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to an explicit YAML scenario configuration.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration only; do not generate artifacts.",
    )
    mode.add_argument(
        "--generate-only",
        action="store_true",
        help="Generate and publish synthetic source CSV files only.",
    )
    mode.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate source CSV files and promote successful Parquet outputs.",
    )
    mode.add_argument(
        "--build-marts-only",
        action="store_true",
        help="Build validated star-schema marts and Python KPI controls.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/synthetic"),
        help="Synthetic CSV destination used with --generate-only.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/synthetic"),
        help="Synthetic CSV source used with --validate-only.",
    )
    parser.add_argument(
        "--validated-dir",
        type=Path,
        default=Path("data/validated"),
        help="Validated Parquet destination used with --validate-only.",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("data/manifest"),
        help="QA evidence destination used with --validate-only.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/data_contract_v1.json"),
        help="Independent data-contract schema used with --validate-only.",
    )
    parser.add_argument(
        "--marts-dir",
        type=Path,
        default=Path("data/marts"),
        help="Analytical Parquet destination used with --build-marts-only.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        config = load_scenario_config(args.config)
    except ConfigurationError as exc:
        print(f"configuration_error: {_sanitized_error(exc)}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR

    preflight = {
        "config_sha256": config.config_sha256,
        "data_class": config.data_class,
        "scenario_id": config.scenario_id,
        "status": "config_valid",
    }

    if args.check_config:
        print(json.dumps(preflight, sort_keys=True))
        return EXIT_OK

    if args.generate_only:
        try:
            generated = generate_synthetic_data(config)
            hashes = publish_synthetic_csvs(generated, args.output_dir)
        except Exception as exc:
            print(f"generation_error: {_sanitized_error(exc)}", file=sys.stderr)
            return EXIT_GENERATION_ERROR
        result = {
            "dataset_build_id": generated.dataset_build_id,
            "files": len(hashes),
            "row_counts": {
                name: len(table) for name, table in generated.tables.items()
            },
            "status": "synthetic_published",
        }
        print(json.dumps(result, sort_keys=True))
        return EXIT_OK

    if args.validate_only:
        try:
            run = validate_and_publish(
                config,
                input_dir=args.input_dir,
                validated_dir=args.validated_dir,
                manifest_dir=args.manifest_dir,
                schema_path=args.schema,
            )
        except Exception as exc:
            print(f"validation_error: {_sanitized_error(exc)}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR
        result = {
            "dataset_build_id": run.outcome.dataset_build_id,
            "execution_id": run.execution_id,
            "failed_gates": sum(
                gate.status == "failed" for gate in run.outcome.results
            ),
            "published": run.published,
            "status": run.outcome.status,
            "total_gates": len(run.outcome.results),
        }
        destination = sys.stdout if run.outcome.passed else sys.stderr
        print(json.dumps(result, sort_keys=True), file=destination)
        return EXIT_OK if run.outcome.passed else EXIT_VALIDATION_FAILED

    if args.build_marts_only:
        try:
            run = build_and_publish_marts(
                config,
                validated_dir=args.validated_dir,
                marts_dir=args.marts_dir,
                manifest_dir=args.manifest_dir,
            )
        except Exception as exc:
            print(f"marts_error: {_sanitized_error(exc)}", file=sys.stderr)
            return EXIT_MARTS_ERROR
        result = {
            "dataset_build_id": run.dataset_build_id,
            "failed_gates": sum(gate.status == "failed" for gate in run.results),
            "marts_execution_id": run.marts_execution_id,
            "published": run.published,
            "status": run.status,
            "tables": len(run.mart_hashes),
            "total_gates": len(run.results),
        }
        destination = sys.stdout if run.status == "passed" else sys.stderr
        print(json.dumps(result, sort_keys=True), file=destination)
        return EXIT_OK if run.status == "passed" else EXIT_MARTS_FAILED

    print(
        "pipeline_not_implemented: generation, validation, and marts are available, "
        "but Power BI is pending the next increment",
        file=sys.stderr,
    )
    return EXIT_PIPELINE_NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main())
