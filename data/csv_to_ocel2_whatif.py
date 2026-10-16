#!/usr/bin/env python3
"""Convert CPN-generated OCEL 2.0 CSV tables to OCEL 2.0 files.

This variant is intended for the thesis what-if/scalability run and uses
separate default output names so that the baseline OCEL files are not
overwritten accidentally.

Default usage:
    1. Put this script in the same folder as the generated CSV files.
    2. Install dependencies once:  python -m pip install pandas pm4py
    3. Run:                        python csv_to_ocel2.py

Outputs:
    intangible_asset_whatif_ocel2.sqlite   (OCEL 2.0 relational/SQLite)
    intangible_asset_whatif_ocel2.jsonocel (OCEL 2.0 JSON)

The converter deliberately loads event/object type tables from the official
mapping CSVs, so helper files such as event_all.csv and object_all.csv are not
mistaken for OCEL type tables.

The final SQLite keeps the official dense relational tables supplied by the
CPN CSV export. In particular, every object-type table keeps ocel_time and
ocel_changed_field. This avoids a lossy PM4Py SQLite re-serialization step that
can produce a database PM4Py can read itself but stricter OCEL 2.0 tools cannot.
The JSONOCEL path is unchanged in principle: PM4Py reads the validated
relational database and writes JSONOCEL. A post-processing step restores
object-attribute timestamps from the validated relational source when PM4Py
replaces them with the Unix epoch, and the repaired JSON is re-imported.

Validation is intentionally fail-fast. Besides referential integrity, the
converter checks exact membership of event/object IDs in their mapped type
specific tables, timestamp syntax, duplicate type mappings, and required OCEL
2.0 relational columns before producing final outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, Set, Tuple

try:
    import pandas as pd
except ImportError as exc:
    raise SystemExit(
        "Missing dependency 'pandas'. Install dependencies with:\n"
        "  python -m pip install pandas pm4py"
    ) from exc

try:
    import pm4py
except ImportError as exc:
    raise SystemExit(
        "Missing dependency 'pm4py'. Install dependencies with:\n"
        "  python -m pip install pandas pm4py"
    ) from exc


CORE_FILES = {
    "event": "event.csv",
    "event_map_type": "event_map_type.csv",
    "event_object": "event_object.csv",
    "object": "object.csv",
    "object_map_type": "object_map_type.csv",
    "object_object": "object_object.csv",
}

REQUIRED_COLUMNS = {
    "event": {"ocel_id", "ocel_type"},
    "event_map_type": {"ocel_type", "ocel_type_map"},
    "event_object": {"ocel_event_id", "ocel_object_id", "ocel_qualifier"},
    "object": {"ocel_id", "ocel_type"},
    "object_map_type": {"ocel_type", "ocel_type_map"},
    "object_object": {"ocel_source_id", "ocel_target_id", "ocel_qualifier"},
}


def read_csv(path: Path) -> pd.DataFrame:
    """Read one semicolon-delimited CPN output CSV."""
    try:
        return pd.read_csv(path, sep=";")
    except Exception as exc:
        raise ValueError(f"Could not read {path.name}: {exc}") from exc


def values_as_strings(df: pd.DataFrame, column: str) -> Set[str]:
    """Return non-null values from one dataframe column as strings."""
    return set(df[column].dropna().astype(str))


def show_values(values: Iterable[str], limit: int = 8) -> str:
    values = sorted(set(values))
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f", ... (+{len(values) - limit} more)"


def require_columns(table_name: str, df: pd.DataFrame, required: Set[str]) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Table '{table_name}' is missing required column(s): "
            f"{', '.join(sorted(missing))}"
        )


def required_nonempty_strings(
    table_name: str, df: pd.DataFrame, column: str
) -> pd.Series:
    """Return a required string column after rejecting null/blank values."""
    if df[column].isna().any():
        raise ValueError(f"{table_name}.csv contains a null value in '{column}'.")

    values = df[column].astype(str).str.strip()
    if (values == "").any():
        raise ValueError(f"{table_name}.csv contains an empty value in '{column}'.")
    return values


def validate_id_column(table_name: str, df: pd.DataFrame) -> None:
    """Reject empty or duplicate OCEL identifiers in a type/core table."""
    ids = required_nonempty_strings(table_name, df, "ocel_id")
    if ids.duplicated().any():
        duplicates = ids[ids.duplicated(keep=False)].tolist()
        raise ValueError(
            f"{table_name}.csv contains duplicate ocel_id value(s): "
            + show_values(duplicates)
        )


def validate_timestamp_column(table_name: str, df: pd.DataFrame) -> None:
    """Reject null, blank, or unparsable OCEL timestamps without rewriting them."""
    if "ocel_time" not in df.columns:
        raise ValueError(f"{table_name}.csv is missing required column 'ocel_time'.")
    if df["ocel_time"].isna().any():
        raise ValueError(f"{table_name}.csv contains a null ocel_time value.")

    raw = df["ocel_time"].astype(str).str.strip()
    if (raw == "").any():
        raise ValueError(f"{table_name}.csv contains an empty ocel_time value.")

    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    invalid = raw[parsed.isna()].tolist()
    if invalid:
        raise ValueError(
            f"{table_name}.csv contains invalid ocel_time value(s): "
            + show_values(invalid)
        )


def load_tables(input_dir: Path) -> Dict[str, pd.DataFrame]:
    """Load core tables and only the type tables named by mapping tables."""
    missing_files = [
        filename for filename in CORE_FILES.values() if not (input_dir / filename).is_file()
    ]
    if missing_files:
        raise FileNotFoundError(
            "Missing required OCEL CSV file(s): " + ", ".join(sorted(missing_files))
        )

    tables: Dict[str, pd.DataFrame] = {}

    for table_name, filename in CORE_FILES.items():
        df = read_csv(input_dir / filename)
        require_columns(table_name, df, REQUIRED_COLUMNS[table_name])
        tables[table_name] = df

    for mapping_table, prefix in (
        ("event_map_type", "event"),
        ("object_map_type", "object"),
    ):
        mapping_df = tables[mapping_table]
        source_types = required_nonempty_strings(
            mapping_table, mapping_df, "ocel_type"
        )
        mapped_names = required_nonempty_strings(
            mapping_table, mapping_df, "ocel_type_map"
        )

        if mapped_names.empty:
            raise ValueError(f"{mapping_table}.csv contains no type mappings.")

        if source_types.duplicated().any():
            duplicates = source_types[source_types.duplicated(keep=False)].tolist()
            raise ValueError(
                f"{mapping_table}.csv contains duplicate ocel_type value(s): "
                f"{show_values(duplicates)}"
            )
        if mapped_names.duplicated().any():
            duplicates = mapped_names[mapped_names.duplicated(keep=False)].tolist()
            raise ValueError(
                f"{mapping_table}.csv contains duplicate ocel_type_map value(s): "
                f"{show_values(duplicates)}"
            )

        for mapped_name in mapped_names.tolist():
            filename = f"{prefix}_{mapped_name}.csv"
            path = input_dir / filename
            if not path.is_file():
                raise FileNotFoundError(
                    f"{mapping_table}.csv declares '{mapped_name}', but {filename} is missing."
                )

            table_name = f"{prefix}_{mapped_name}"
            df = read_csv(path)
            if prefix == "event":
                require_columns(table_name, df, {"ocel_id", "ocel_time"})
            else:
                require_columns(
                    table_name, df, {"ocel_id", "ocel_time", "ocel_changed_field"}
                )
            tables[table_name] = df

    return tables


def validate_tables(tables: Dict[str, pd.DataFrame]) -> None:
    """Perform structural, timestamp, referential, and exact type-table checks."""
    events = tables["event"]
    objects = tables["object"]

    validate_id_column("event", events)
    validate_id_column("object", objects)
    required_nonempty_strings("event", events, "ocel_type")
    required_nonempty_strings("object", objects, "ocel_type")

    event_ids = values_as_strings(events, "ocel_id")
    object_ids = values_as_strings(objects, "ocel_id")

    e2o = tables["event_object"]
    e2o_event_ids = required_nonempty_strings(
        "event_object", e2o, "ocel_event_id"
    )
    e2o_object_ids = required_nonempty_strings(
        "event_object", e2o, "ocel_object_id"
    )
    missing_e2o_events = set(e2o_event_ids) - event_ids
    missing_e2o_objects = set(e2o_object_ids) - object_ids
    if missing_e2o_events:
        raise ValueError(
            "event_object.csv references unknown event ID(s): "
            + show_values(missing_e2o_events)
        )
    if missing_e2o_objects:
        raise ValueError(
            "event_object.csv references unknown object ID(s): "
            + show_values(missing_e2o_objects)
        )

    o2o = tables["object_object"]
    o2o_source_ids = required_nonempty_strings(
        "object_object", o2o, "ocel_source_id"
    )
    o2o_target_ids = required_nonempty_strings(
        "object_object", o2o, "ocel_target_id"
    )
    missing_o2o_sources = set(o2o_source_ids) - object_ids
    missing_o2o_targets = set(o2o_target_ids) - object_ids
    if missing_o2o_sources:
        raise ValueError(
            "object_object.csv references unknown source object ID(s): "
            + show_values(missing_o2o_sources)
        )
    if missing_o2o_targets:
        raise ValueError(
            "object_object.csv references unknown target object ID(s): "
            + show_values(missing_o2o_targets)
        )

    # Every core event/object must be represented in exactly the type table
    # declared by its mapping row. Exact membership catches both missing IDs
    # and IDs accidentally placed in the wrong type-specific table.
    for core_name, mapping_name, prefix in (
        ("event", "event_map_type", "event"),
        ("object", "object_map_type", "object"),
    ):
        core = tables[core_name]
        mapping = tables[mapping_name]

        source_types = required_nonempty_strings(
            mapping_name, mapping, "ocel_type"
        )
        mapped_names = required_nonempty_strings(
            mapping_name, mapping, "ocel_type_map"
        )

        if source_types.duplicated().any():
            duplicates = source_types[source_types.duplicated(keep=False)].tolist()
            raise ValueError(
                f"{mapping_name}.csv contains duplicate ocel_type value(s): "
                + show_values(duplicates)
            )
        if mapped_names.duplicated().any():
            duplicates = mapped_names[mapped_names.duplicated(keep=False)].tolist()
            raise ValueError(
                f"{mapping_name}.csv contains duplicate ocel_type_map value(s): "
                + show_values(duplicates)
            )

        mapping_pairs = list(zip(source_types.tolist(), mapped_names.tolist()))
        mapped_types = {source_type for source_type, _ in mapping_pairs}
        core_types = set(required_nonempty_strings(core_name, core, "ocel_type"))
        unmapped_types = core_types - mapped_types
        if unmapped_types:
            raise ValueError(
                f"{core_name}.csv contains type(s) not declared in {mapping_name}.csv: "
                + show_values(unmapped_types)
            )

        for source_type, mapped_name in mapping_pairs:
            expected_ids = set(
                core.loc[
                    core["ocel_type"].astype(str).str.strip() == source_type,
                    "ocel_id",
                ]
                .dropna()
                .astype(str)
            )
            type_table_name = f"{prefix}_{mapped_name}"
            type_table = tables[type_table_name]
            validate_id_column(type_table_name, type_table)
            validate_timestamp_column(type_table_name, type_table)
            actual_ids = values_as_strings(type_table, "ocel_id")

            missing_ids = expected_ids - actual_ids
            unexpected_ids = actual_ids - expected_ids
            if missing_ids:
                raise ValueError(
                    f"{type_table_name}.csv is missing expected ID(s) for "
                    f"OCEL type '{source_type}': " + show_values(missing_ids)
                )
            if unexpected_ids:
                raise ValueError(
                    f"{type_table_name}.csv contains ID(s) that do not belong to "
                    f"OCEL type '{source_type}': " + show_values(unexpected_ids)
                )


def write_staging_sqlite(tables: Dict[str, pd.DataFrame], path: Path) -> None:
    """Write the CPN CSV tables into the relational OCEL table layout."""
    if path.exists():
        path.unlink()

    with sqlite3.connect(path) as connection:
        for table_name, df in tables.items():
            df.to_sql(table_name, connection, index=False, if_exists="replace")
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {result}")


def quote_identifier(identifier: str) -> str:
    """Quote one SQLite identifier without treating mapping data as SQL."""
    return '"' + identifier.replace('"', '""') + '"'


def sqlite_table_columns(connection: sqlite3.Connection, table_name: str) -> Set[str]:
    """Return the column names declared for one SQLite table."""
    query = f"PRAGMA table_info({quote_identifier(table_name)})"
    return {str(row[1]) for row in connection.execute(query)}


def validate_relational_sqlite(path: Path) -> None:
    """Validate the final relational OCEL structure and type-table membership.

    PM4Py round-trip validation alone is insufficient because the same PM4Py
    reader may accept a file produced by its writer even when required dense
    object-table columns have been omitted. This independent check protects
    interoperability with OCPQ and other OCEL 2.0 tools.
    """
    with sqlite3.connect(path) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")

        table_names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

        for table_name, required in REQUIRED_COLUMNS.items():
            if table_name not in table_names:
                raise ValueError(f"SQLite output is missing core table '{table_name}'.")
            missing = required - sqlite_table_columns(connection, table_name)
            if missing:
                raise ValueError(
                    f"SQLite table '{table_name}' is missing required column(s): "
                    + ", ".join(sorted(missing))
                )

        # Recheck core identifier uniqueness in the actual final database.
        for core_table in ("event", "object"):
            duplicates = connection.execute(
                f"SELECT ocel_id FROM {quote_identifier(core_table)} "
                "GROUP BY ocel_id HAVING COUNT(*) > 1"
            ).fetchall()
            if duplicates:
                raise ValueError(
                    f"SQLite table '{core_table}' contains duplicate ocel_id value(s): "
                    + show_values(str(row[0]) for row in duplicates)
                )

        mapping_specs = (
            ("event_map_type", "event", {"ocel_id", "ocel_time"}),
            (
                "object_map_type",
                "object",
                {"ocel_id", "ocel_time", "ocel_changed_field"},
            ),
        )

        for mapping_table, prefix, required in mapping_specs:
            mapping_rows = connection.execute(
                f"SELECT ocel_type, ocel_type_map FROM {quote_identifier(mapping_table)}"
            ).fetchall()
            if not mapping_rows:
                raise ValueError(f"SQLite table '{mapping_table}' contains no mappings.")

            seen_source_types: Set[str] = set()
            seen_mapped_names: Set[str] = set()
            for source_type, mapped_name in mapping_rows:
                if source_type is None or mapped_name is None:
                    raise ValueError(
                        f"SQLite table '{mapping_table}' contains a null mapping value."
                    )

                source_type = str(source_type).strip()
                mapped_name = str(mapped_name).strip()
                if not source_type or not mapped_name:
                    raise ValueError(
                        f"SQLite table '{mapping_table}' contains an empty mapping value."
                    )
                if source_type in seen_source_types:
                    raise ValueError(
                        f"SQLite table '{mapping_table}' contains duplicate source type "
                        f"'{source_type}'."
                    )
                if mapped_name in seen_mapped_names:
                    raise ValueError(
                        f"SQLite table '{mapping_table}' maps more than one row to "
                        f"'{mapped_name}'."
                    )
                seen_source_types.add(source_type)
                seen_mapped_names.add(mapped_name)

                type_table = f"{prefix}_{mapped_name}"
                if type_table not in table_names:
                    raise ValueError(
                        f"SQLite mapping '{source_type}' points to missing table "
                        f"'{type_table}'."
                    )

                missing = required - sqlite_table_columns(connection, type_table)
                if missing:
                    raise ValueError(
                        f"SQLite table '{type_table}' is missing required OCEL 2.0 "
                        f"column(s): {', '.join(sorted(missing))}"
                    )

                duplicate_type_ids = connection.execute(
                    f"SELECT ocel_id FROM {quote_identifier(type_table)} "
                    "GROUP BY ocel_id HAVING COUNT(*) > 1"
                ).fetchall()
                if duplicate_type_ids:
                    raise ValueError(
                        f"SQLite table '{type_table}' contains duplicate ocel_id value(s): "
                        + show_values(str(row[0]) for row in duplicate_type_ids)
                    )

                expected_ids = {
                    str(row[0])
                    for row in connection.execute(
                        f"SELECT ocel_id FROM {quote_identifier(prefix)} "
                        "WHERE TRIM(CAST(ocel_type AS TEXT)) = ?",
                        (source_type,),
                    ).fetchall()
                }
                actual_ids = {
                    str(row[0])
                    for row in connection.execute(
                        f"SELECT ocel_id FROM {quote_identifier(type_table)}"
                    ).fetchall()
                }
                missing_ids = expected_ids - actual_ids
                unexpected_ids = actual_ids - expected_ids
                if missing_ids:
                    raise ValueError(
                        f"SQLite table '{type_table}' is missing ID(s) for type "
                        f"'{source_type}': " + show_values(missing_ids)
                    )
                if unexpected_ids:
                    raise ValueError(
                        f"SQLite table '{type_table}' contains ID(s) that do not belong "
                        f"to type '{source_type}': " + show_values(unexpected_ids)
                    )

                time_rows = connection.execute(
                    f"SELECT ocel_time FROM {quote_identifier(type_table)}"
                ).fetchall()
                validate_timestamp_column(
                    type_table,
                    pd.DataFrame({"ocel_time": [row[0] for row in time_rows]}),
                )

        print("Official OCEL 2.0 relational table structure and membership: OK")


def normalized_json_value(value: Any) -> Tuple[str, str]:
    """Return a stable key for matching JSON and SQLite scalar values."""
    if value is None:
        return ("null", "")
    if isinstance(value, bool):
        return ("bool", "true" if value else "false")
    if isinstance(value, (int, float)):
        return ("number", format(float(value), ".15g"))
    return ("string", str(value))


def repair_json_object_attribute_times(json_path: Path, sqlite_path: Path) -> int:
    """Restore JSON object-attribute timestamps from the validated SQLite log.

    Some PM4Py versions replace object-attribute timestamps by the Unix epoch
    while converting an OCEL 2.0 SQLite log to JSONOCEL. The relational source
    still contains the original ocel_time values. This function reconstructs
    attribute occurrences from the dense relational tables and restores their
    timestamps in JSON.

    For an initial dense object row (empty ocel_changed_field), each non-null
    attribute value is an initial attribute occurrence. For a change row, only
    the attribute named by ocel_changed_field is treated as a new occurrence.
    This avoids duplicating unchanged dense values when dynamic attributes are
    present. Only object-attribute ``time`` members are modified.
    """
    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    original_events = payload.get("events")
    original_object_shells = [
        {key: value for key, value in obj.items() if key != "attributes"}
        for obj in payload.get("objects", [])
    ]
    original_attribute_values = [
        [
            {key: value for key, value in attribute.items() if key != "time"}
            for attribute in obj.get("attributes", [])
        ]
        for obj in payload.get("objects", [])
    ]

    exact_candidates: Dict[
        Tuple[str, str, Tuple[str, str]], Deque[str]
    ] = defaultdict(deque)

    with sqlite3.connect(sqlite_path) as connection:
        mappings = connection.execute(
            "SELECT ocel_type, ocel_type_map FROM object_map_type"
        ).fetchall()

        for _, mapped_type in mappings:
            table_name = f"object_{mapped_type}"
            columns = [
                row[1]
                for row in connection.execute(
                    f"PRAGMA table_info({quote_identifier(table_name)})"
                ).fetchall()
            ]
            attribute_columns = [
                column
                for column in columns
                if column not in {"ocel_id", "ocel_time", "ocel_changed_field"}
            ]
            if not attribute_columns:
                continue

            selected = ", ".join(quote_identifier(column) for column in columns)
            rows = connection.execute(
                f"SELECT {selected} FROM {quote_identifier(table_name)} "
                "ORDER BY ocel_id, ocel_time"
            ).fetchall()
            index = {column: position for position, column in enumerate(columns)}

            for row in rows:
                object_id = str(row[index["ocel_id"]])
                timestamp = row[index["ocel_time"]]
                if timestamp is None:
                    raise ValueError(
                        f"SQLite table '{table_name}' contains a null ocel_time for "
                        f"object '{object_id}'."
                    )
                timestamp = str(timestamp)

                changed_field = row[index["ocel_changed_field"]]
                changed_field = (
                    "" if changed_field is None else str(changed_field).strip()
                )

                if changed_field:
                    if changed_field not in attribute_columns:
                        raise ValueError(
                            f"SQLite table '{table_name}' contains unknown "
                            f"ocel_changed_field '{changed_field}' for object "
                            f"'{object_id}'."
                        )
                    candidate_attributes = [changed_field]
                else:
                    candidate_attributes = attribute_columns

                for attribute_name in candidate_attributes:
                    value = row[index[attribute_name]]
                    if value is None:
                        continue
                    exact_candidates[
                        (object_id, attribute_name, normalized_json_value(value))
                    ].append(timestamp)

    repaired = 0
    unmatched = []
    for obj in payload.get("objects", []):
        object_id = str(obj.get("id"))
        for attribute in obj.get("attributes", []):
            attribute_name = str(attribute.get("name"))
            exact_key = (
                object_id,
                attribute_name,
                normalized_json_value(attribute.get("value")),
            )
            candidates = exact_candidates.get(exact_key)
            if candidates:
                timestamp = candidates.popleft()
            else:
                unmatched.append(f"{object_id}.{attribute_name}")
                continue
            if attribute.get("time") != timestamp:
                attribute["time"] = timestamp
                repaired += 1

    if unmatched:
        raise ValueError(
            "Could not restore SQLite timestamps for JSON object attribute(s): "
            + show_values(unmatched)
        )

    leftovers = []
    for (object_id, attribute_name, _), candidates in exact_candidates.items():
        if candidates:
            leftovers.append(
                f"{object_id}.{attribute_name} ({len(candidates)} unmatched occurrence(s))"
            )
    if leftovers:
        raise ValueError(
            "SQLite contains object-attribute occurrence(s) not represented in JSON: "
            + show_values(leftovers)
        )

    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    # Post-write invariants: only object-attribute times may differ.
    with json_path.open("r", encoding="utf-8") as handle:
        verified = json.load(handle)
    if verified.get("events") != original_events:
        raise ValueError("JSON repair changed events or event relationships.")
    verified_shells = [
        {key: value for key, value in obj.items() if key != "attributes"}
        for obj in verified.get("objects", [])
    ]
    verified_attribute_values = [
        [
            {key: value for key, value in attribute.items() if key != "time"}
            for attribute in obj.get("attributes", [])
        ]
        for obj in verified.get("objects", [])
    ]
    if verified_shells != original_object_shells:
        raise ValueError("JSON repair changed object identities or relationships.")
    if verified_attribute_values != original_attribute_values:
        raise ValueError("JSON repair changed object attribute names or values.")

    repaired_times = [
        attribute.get("time")
        for obj in verified.get("objects", [])
        for attribute in obj.get("attributes", [])
    ]
    if repaired_times:
        validate_timestamp_column(
            "JSON object attributes",
            pd.DataFrame({"ocel_time": repaired_times}),
        )

    return repaired


def convert(input_dir: Path, sqlite_output: Path, json_output: Path | None) -> None:
    print(f"Input directory: {input_dir}")
    print("Loading CSV tables...")
    tables = load_tables(input_dir)
    validate_tables(tables)

    print(f"Validated {len(tables)} OCEL tables.")
    print(f"Events: {len(tables['event'])}")
    print(f"Objects: {len(tables['object'])}")
    print(f"E2O relations: {len(tables['event_object'])}")
    print(f"O2O relations: {len(tables['object_object'])}")

    staging_path = input_dir / "_ocel2_conversion_staging.sqlite"
    if staging_path == sqlite_output:
        staging_path = input_dir / "_ocel2_conversion_staging.tmp.sqlite"

    try:
        print("Building relational OCEL 2.0 database...")
        write_staging_sqlite(tables, staging_path)

        print("Checking the official OCEL 2.0 relational table structure...")
        validate_relational_sqlite(staging_path)

        print("Validating the database with PM4Py...")
        print(f"PM4Py version: {getattr(pm4py, '__version__', 'unknown')}")
        ocel = pm4py.read_ocel2_sqlite(str(staging_path))
        print(ocel.get_summary())

        # Preserve the validated official relational schema exactly. Do not
        # rewrite the database with pm4py.write_ocel2_sqlite(): some PM4Py
        # versions omit ocel_time and ocel_changed_field from object-type
        # tables, which can make the result unreadable by stricter tools.
        if sqlite_output.exists():
            sqlite_output.unlink()
        os.replace(staging_path, sqlite_output)

        # Validate the actual final file independently and with PM4Py.
        validate_relational_sqlite(sqlite_output)
        pm4py.read_ocel2_sqlite(str(sqlite_output))
        print(f"Created and verified: {sqlite_output.name}")

        if json_output is not None:
            if json_output.exists():
                json_output.unlink()
            pm4py.write_ocel2_json(ocel, str(json_output))
            repaired = repair_json_object_attribute_times(json_output, sqlite_output)
            print(f"Restored {repaired} JSON object-attribute timestamp(s).")
            pm4py.read_ocel2_json(str(json_output))
            print(f"Created and verified: {json_output.name}")

    finally:
        if staging_path.exists():
            staging_path.unlink()


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=(
            "Convert CPN-generated semicolon-delimited OCEL CSV tables to "
            "OCEL 2.0 SQLite and JSONOCEL files."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=script_dir,
        help="Directory containing the CSV files (default: script directory).",
    )
    parser.add_argument(
        "--sqlite",
        default="intangible_asset_whatif_ocel2.sqlite",
        help="SQLite output filename (default: intangible_asset_whatif_ocel2.sqlite).",
    )
    parser.add_argument(
        "--json",
        default="intangible_asset_whatif_ocel2.jsonocel",
        help="JSONOCEL output filename (default: intangible_asset_whatif_ocel2.jsonocel).",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Create only the OCEL 2.0 SQLite file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.expanduser().resolve()

    if not input_dir.is_dir():
        print(f"ERROR: Input directory does not exist: {input_dir}", file=sys.stderr)
        return 1

    sqlite_output = input_dir / args.sqlite
    json_output = None if args.no_json else input_dir / args.json

    try:
        convert(input_dir, sqlite_output, json_output)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    print("\nConversion completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
