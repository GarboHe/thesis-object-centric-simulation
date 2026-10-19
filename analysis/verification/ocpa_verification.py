from pathlib import Path

import pandas as pd
from ocpa.objects.log.importer.ocel import factory as ocel_import_factory


# ============================================================
# 0. PATHS
# ============================================================

# Repository layout:
#   data/ocpa_all_types.jsonocel
#   analysis/verification/ocpa_verification.py
#
# Resolve paths from this script's location so the script works
# regardless of where the repository is cloned.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

FILE_PATH = REPO_ROOT / "data" / "ocpa_all_types.jsonocel"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if not FILE_PATH.is_file():
    raise FileNotFoundError(
        "The input OCEL file was not found:\n"
        f"  {FILE_PATH}\n"
        "Check that the repository contains data/ocpa_all_types.jsonocel."
    )

print(f"Loading OCEL from: {FILE_PATH}")
ocpa_log = ocel_import_factory.apply(str(FILE_PATH))
print("OCEL successfully loaded.")


# ============================================================
# Verification:
# Activity × Object Type Count / Cardinality Matrices
# ============================================================

df = ocpa_log.log.log.copy()

OBJECT_TYPES = [
    "AcceptanceRecord",
    "Asset",
    "Invoice",
    "Order",
    "Project",
    "Requirement",
    "Resource",
    "Supplier",
    "Voucher",
]


# ------------------------------------------------------------
# Helper
# ------------------------------------------------------------

def as_list(value):
    if value is None:
        return []

    if isinstance(value, (list, set, tuple)):
        return list(value)

    try:
        if pd.isna(value):
            return []
    except Exception:
        pass

    return [value]


# ============================================================
# 1. EVENT-LEVEL CARDINALITY TABLE
#
# One row = one event
# Each object-type column = number of objects of that type
# ============================================================

rows = []

for _, row in df.iterrows():
    result = {
        "event_activity": row["event_activity"]
    }

    if "event_id" in df.columns:
        result["event_id"] = row["event_id"]

    for object_type in OBJECT_TYPES:
        if object_type in df.columns:
            result[object_type] = len(as_list(row[object_type]))
        else:
            result[object_type] = 0

    rows.append(result)

event_cardinality = pd.DataFrame(rows)

print("\nEVENT-LEVEL CARDINALITY:")
print(event_cardinality.head().to_string(index=False))


# ============================================================
# 2. ACTIVITY FREQUENCY
# ============================================================

activity_frequency = (
    event_cardinality
    .groupby("event_activity")
    .size()
    .rename("event_count")
    .reset_index()
)

print("\nACTIVITY FREQUENCY:")
print(activity_frequency.to_string(index=False))


# ============================================================
# 3. RELATION COUNT MATRIX
#
# Cell meaning:
# Total number of Event-to-Object relations
#
# Example:
# 30 Obtain Quotations events
# total Supplier relations = 72
# ============================================================

relation_count_matrix = (
    event_cardinality
    .groupby("event_activity")[OBJECT_TYPES]
    .sum()
)

print("\n====================================")
print("RELATION COUNT MATRIX")
print("====================================")
print(relation_count_matrix.to_string())


# ============================================================
# 4. MIN CARDINALITY MATRIX
# ============================================================

min_cardinality_matrix = (
    event_cardinality
    .groupby("event_activity")[OBJECT_TYPES]
    .min()
)


# ============================================================
# 5. MAX CARDINALITY MATRIX
# ============================================================

max_cardinality_matrix = (
    event_cardinality
    .groupby("event_activity")[OBJECT_TYPES]
    .max()
)


# ============================================================
# 6. MEAN CARDINALITY MATRIX
# ============================================================

mean_cardinality_matrix = (
    event_cardinality
    .groupby("event_activity")[OBJECT_TYPES]
    .mean()
    .round(2)
)


# ============================================================
# 7. CARDINALITY RANGE MATRIX
#
# Cell examples:
# 0
# 1
# 0-1
# 2-3
#
# This is the most useful one for thesis Verification.
# ============================================================

cardinality_range_matrix = pd.DataFrame(
    index=min_cardinality_matrix.index,
    columns=OBJECT_TYPES
)

for activity in cardinality_range_matrix.index:
    for object_type in OBJECT_TYPES:
        min_value = int(
            min_cardinality_matrix.loc[activity, object_type]
        )
        max_value = int(
            max_cardinality_matrix.loc[activity, object_type]
        )

        # No relation at all
        if min_value == 0 and max_value == 0:
            value = "-"

        # Fixed cardinality
        elif min_value == max_value:
            value = str(min_value)

        # Variable cardinality
        else:
            value = f"{min_value}-{max_value}"

        cardinality_range_matrix.loc[activity, object_type] = value

print("\n====================================")
print("CARDINALITY RANGE MATRIX")
print("====================================")
print(cardinality_range_matrix.to_string())


# ============================================================
# 8. COMBINED VERIFICATION TABLE
#
# Format:
# relation count [cardinality]
#
# Examples:
# 72 [2-3]
# 30 [1]
# 25 [0-1]
# ============================================================

combined_matrix = pd.DataFrame(
    index=relation_count_matrix.index,
    columns=OBJECT_TYPES
)

for activity in combined_matrix.index:
    for object_type in OBJECT_TYPES:
        rel_count = int(
            relation_count_matrix.loc[activity, object_type]
        )
        card = cardinality_range_matrix.loc[activity, object_type]

        if rel_count == 0:
            combined_matrix.loc[activity, object_type] = "-"
        else:
            combined_matrix.loc[activity, object_type] = f"{rel_count} [{card}]"

print("\n====================================")
print("COMBINED VERIFICATION MATRIX")
print("====================================")
print(combined_matrix.to_string())


# ============================================================
# 9. SAVE CSV OUTPUTS
# ============================================================

relation_count_matrix.to_csv(
    OUTPUT_DIR / "activity_object_relation_count_matrix.csv"
)

cardinality_range_matrix.to_csv(
    OUTPUT_DIR / "activity_object_cardinality_matrix.csv"
)

mean_cardinality_matrix.to_csv(
    OUTPUT_DIR / "activity_object_mean_cardinality_matrix.csv"
)

combined_matrix.to_csv(
    OUTPUT_DIR / "activity_object_combined_verification_matrix.csv"
)


# ============================================================
# 10. SAVE EXCEL OUTPUT
# ============================================================

excel_path = OUTPUT_DIR / "Verification_Matrices.xlsx"

with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
    event_cardinality.to_excel(
        writer,
        sheet_name="Event_Cardinality",
        index=False
    )

    activity_frequency.to_excel(
        writer,
        sheet_name="Activity_Frequency",
        index=False
    )

    relation_count_matrix.to_excel(
        writer,
        sheet_name="Relation_Count"
    )

    min_cardinality_matrix.to_excel(
        writer,
        sheet_name="Min_Cardinality"
    )

    max_cardinality_matrix.to_excel(
        writer,
        sheet_name="Max_Cardinality"
    )

    mean_cardinality_matrix.to_excel(
        writer,
        sheet_name="Mean_Cardinality"
    )

    cardinality_range_matrix.to_excel(
        writer,
        sheet_name="Cardinality_Range"
    )

    combined_matrix.to_excel(
        writer,
        sheet_name="Combined_Verification"
    )

print("\nVerification matrices saved to:")
print(OUTPUT_DIR.resolve())
print("\nExcel:")
print(excel_path.resolve())
