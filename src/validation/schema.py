"""Independent schema loading and logical type conversion for source CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

import pandas as pd


SUPPORTED_TYPES = {"string", "boolean", "integer", "number", "date", "datetime"}
_OFFSET_PATTERN = re.compile(r"(?:Z|[+-][0-9]{2}:[0-9]{2})$")


class SchemaDefinitionError(ValueError):
    """Raised when the independent schema artifact is malformed."""


@dataclass(frozen=True)
class ColumnContract:
    name: str
    logical_type: str
    nullable: bool
    enum: tuple[str, ...] = ()
    pattern: str | None = None


@dataclass(frozen=True)
class DatasetContract:
    name: str
    primary_key: tuple[str, ...]
    columns: tuple[ColumnContract, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)


@dataclass(frozen=True)
class DataContractSchema:
    schema_version: str
    datasets: Mapping[str, DatasetContract]


@dataclass(frozen=True)
class SchemaFinding:
    dataset: str
    code: str
    violation_count: int
    message: str


@dataclass(frozen=True)
class LoadedSource:
    tables: Mapping[str, pd.DataFrame]
    findings: tuple[SchemaFinding, ...]


def load_contract_schema(path: str | Path) -> DataContractSchema:
    schema_path = Path(path)
    try:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SchemaDefinitionError(f"cannot load schema: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("datasets"), dict):
        raise SchemaDefinitionError("schema root must contain a datasets mapping")
    version = payload.get("schema_version")
    if not isinstance(version, str) or not version:
        raise SchemaDefinitionError("schema_version must be a non-empty string")

    datasets: dict[str, DatasetContract] = {}
    for dataset_name, dataset_payload in payload["datasets"].items():
        if not isinstance(dataset_payload, dict):
            raise SchemaDefinitionError(f"{dataset_name}: definition must be a mapping")
        primary_key = dataset_payload.get("primary_key")
        column_payloads = dataset_payload.get("columns")
        if not isinstance(primary_key, list) or not primary_key:
            raise SchemaDefinitionError(f"{dataset_name}: primary_key is required")
        if not isinstance(column_payloads, list) or not column_payloads:
            raise SchemaDefinitionError(f"{dataset_name}: columns are required")

        columns: list[ColumnContract] = []
        for item in column_payloads:
            if not isinstance(item, dict):
                raise SchemaDefinitionError(f"{dataset_name}: invalid column definition")
            name = item.get("name")
            logical_type = item.get("type")
            nullable = item.get("nullable")
            if not isinstance(name, str) or not name:
                raise SchemaDefinitionError(f"{dataset_name}: column name is required")
            if logical_type not in SUPPORTED_TYPES:
                raise SchemaDefinitionError(
                    f"{dataset_name}.{name}: unsupported type {logical_type}"
                )
            if not isinstance(nullable, bool):
                raise SchemaDefinitionError(
                    f"{dataset_name}.{name}: nullable must be boolean"
                )
            enum = item.get("enum", [])
            pattern = item.get("pattern")
            if not isinstance(enum, list) or not all(
                isinstance(value, str) for value in enum
            ):
                raise SchemaDefinitionError(f"{dataset_name}.{name}: invalid enum")
            if pattern is not None:
                if not isinstance(pattern, str):
                    raise SchemaDefinitionError(f"{dataset_name}.{name}: invalid pattern")
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise SchemaDefinitionError(
                        f"{dataset_name}.{name}: invalid pattern: {exc}"
                    ) from exc
            columns.append(
                ColumnContract(
                    name=name,
                    logical_type=logical_type,
                    nullable=nullable,
                    enum=tuple(enum),
                    pattern=pattern,
                )
            )

        names = [column.name for column in columns]
        if len(names) != len(set(names)):
            raise SchemaDefinitionError(f"{dataset_name}: duplicate column names")
        if not set(primary_key) <= set(names):
            raise SchemaDefinitionError(f"{dataset_name}: PK references unknown columns")
        datasets[dataset_name] = DatasetContract(
            name=dataset_name,
            primary_key=tuple(primary_key),
            columns=tuple(columns),
        )

    return DataContractSchema(schema_version=version, datasets=datasets)


def _header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return next(csv.reader(source), [])


def _convert_column(
    raw: pd.Series,
    contract: ColumnContract,
) -> tuple[pd.Series, list[tuple[str, int, str]]]:
    text = raw.astype("string")
    blank = text.isna() | text.str.strip().eq("")
    findings: list[tuple[str, int, str]] = []
    if not contract.nullable and int(blank.sum()):
        findings.append(
            ("required", int(blank.sum()), f"{contract.name} contains null or blank values")
        )

    if contract.logical_type == "string":
        converted = text.mask(blank, pd.NA)
        invalid_type = pd.Series(False, index=text.index)
    elif contract.logical_type == "boolean":
        normalized = text.str.strip().str.lower()
        converted = normalized.map({"true": True, "false": False}).astype("boolean")
        invalid_type = ~blank & converted.isna()
    elif contract.logical_type in {"integer", "number"}:
        converted = pd.to_numeric(text.mask(blank, pd.NA), errors="coerce")
        invalid_type = ~blank & converted.isna()
        if contract.logical_type == "integer":
            non_integer = converted.notna() & converted.mod(1).ne(0)
            invalid_type |= non_integer
            converted = converted.astype("Float64").mask(non_integer, pd.NA).astype("Int64")
        else:
            converted = converted.astype("Float64")
    elif contract.logical_type == "date":
        format_ok = text.str.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", na=False)
        converted = pd.to_datetime(text.mask(blank, pd.NA), format="%Y-%m-%d", errors="coerce")
        invalid_type = ~blank & (~format_ok | converted.isna())
    else:
        offset_ok = text.map(
            lambda value: bool(_OFFSET_PATTERN.search(str(value))) if pd.notna(value) else False
        )
        converted = pd.to_datetime(text.mask(blank, pd.NA), utc=True, errors="coerce")
        invalid_type = ~blank & (~offset_ok | converted.isna())

    invalid_count = int(invalid_type.sum())
    if invalid_count:
        findings.append(
            ("logical_type", invalid_count, f"{contract.name} violates {contract.logical_type}")
        )

    valid_text = text.mask(blank, pd.NA)
    if contract.enum:
        invalid_enum = valid_text.notna() & ~valid_text.isin(contract.enum)
        if int(invalid_enum.sum()):
            findings.append(
                (
                    "enum",
                    int(invalid_enum.sum()),
                    f"{contract.name} contains values outside its controlled domain",
                )
            )
    if contract.pattern:
        invalid_pattern = valid_text.notna() & ~valid_text.str.fullmatch(
            contract.pattern,
            na=False,
        )
        if int(invalid_pattern.sum()):
            findings.append(
                (
                    "pattern",
                    int(invalid_pattern.sum()),
                    f"{contract.name} contains malformed identifiers",
                )
            )
    return converted, findings


def load_source_tables(
    input_dir: str | Path,
    schema: DataContractSchema,
) -> LoadedSource:
    source_dir = Path(input_dir)
    findings: list[SchemaFinding] = []
    tables: dict[str, pd.DataFrame] = {}
    expected_names = set(schema.datasets)
    actual_names = {path.stem for path in source_dir.glob("*.csv")} if source_dir.is_dir() else set()

    for extra in sorted(actual_names - expected_names):
        findings.append(
            SchemaFinding(extra, "unexpected_dataset", 1, "unexpected CSV dataset")
        )

    for name, dataset in schema.datasets.items():
        path = source_dir / f"{name}.csv"
        if not path.is_file():
            findings.append(
                SchemaFinding(name, "missing_dataset", 1, "required CSV dataset is missing")
            )
            tables[name] = pd.DataFrame(columns=dataset.column_names)
            continue

        header = _header(path)
        if len(header) != len(set(header)):
            findings.append(
                SchemaFinding(name, "duplicate_columns", 1, "CSV header has duplicate columns")
            )
        missing = sorted(set(dataset.column_names) - set(header))
        extra = sorted(set(header) - set(dataset.column_names))
        if missing:
            findings.append(
                SchemaFinding(
                    name,
                    "missing_columns",
                    len(missing),
                    "missing columns: " + ", ".join(missing),
                )
            )
        if extra:
            findings.append(
                SchemaFinding(
                    name,
                    "unexpected_columns",
                    len(extra),
                    "unexpected columns: " + ", ".join(extra),
                )
            )
        if header != list(dataset.column_names):
            findings.append(
                SchemaFinding(name, "column_order", 1, "column order differs from schema")
            )

        try:
            raw = pd.read_csv(
                path,
                dtype="string",
                keep_default_na=False,
                na_filter=False,
                encoding="utf-8",
            )
        except (OSError, UnicodeError, pd.errors.ParserError) as exc:
            findings.append(
                SchemaFinding(name, "csv_parse", 1, f"cannot parse CSV: {type(exc).__name__}")
            )
            tables[name] = pd.DataFrame(columns=dataset.column_names)
            continue

        for missing_column in missing:
            raw[missing_column] = ""
        typed = pd.DataFrame(index=raw.index)
        for column in dataset.columns:
            converted, column_findings = _convert_column(raw[column.name], column)
            typed[column.name] = converted
            for code, count, message in column_findings:
                findings.append(SchemaFinding(name, code, count, message))
        tables[name] = typed.loc[:, dataset.column_names]

    return LoadedSource(tables=tables, findings=tuple(findings))
