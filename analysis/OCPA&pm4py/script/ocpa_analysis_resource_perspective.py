# ============================================================
# BQ4 - OCPA Focused Interaction Analysis
#
# Research question:
# Where do shared actors interact with multiple business objects?
#
# Input:
# OCEL 1.0 .jsonocel containing Resource and Supplier
#
# Output:
# results/BQ4/OCPA/
#     01_actor_object_interactions.csv
#     02_actor_event_interaction.csv
#     03_multi_object_events.csv
#     04_BQ4_interaction_hotspots.csv
#     05_actor_object_summary.csv
#     06_actor_overall_summary.csv
#     07_activity_hotspots.csv
#     BQ4_OCPA_results.xlsx
# ============================================================

import argparse
import os
from pathlib import Path

import pandas as pd

from ocpa.objects.log.importer.ocel import factory as ocel_import_factory

def show(df, n=None):
    if n is not None:
        df = df.head(n)
    print(df.to_string(index=False))
# ============================================================
# 1. COMMAND-LINE ARGUMENTS
# ============================================================

parser = argparse.ArgumentParser(
    description="Run BQ4 OCPA focused interaction analysis."
)

parser.add_argument(
    "--input",
    required=True,
    help="Path to the OCPA-compatible OCEL 1.0 JSONOCEL file."
)

parser.add_argument(
    "--out",
    default="results/BQ4/OCPA",
    help="Output directory for BQ4 OCPA result files."
)

args = parser.parse_args()

FILE_PATH = Path(args.input)
OUTPUT_DIR = Path(args.out)

if not FILE_PATH.exists():
    raise FileNotFoundError(
        f"Input file not found: {FILE_PATH}"
    )

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 3. IMPORT JSONOCEL INTO OCPA
# ============================================================

print("Loading OCEL into OCPA...")

ocpa_log = ocel_import_factory.apply(
    FILE_PATH
)

print("OCPA log successfully loaded.")


# ============================================================
# 4. GET EVENT-LEVEL DATAFRAME
# ============================================================

df = ocpa_log.log.log.copy()

print("\n=====================================")
print("OCPA EVENT TABLE")
print("=====================================")

print("Number of events:", len(df))

print("\nColumns:")
print(df.columns.tolist())

print("\nFirst rows:")
show(df.head())


# ============================================================
# 5. DEFINE ACTORS AND BUSINESS OBJECTS
# ============================================================

# Actor types for BQ4
ACTOR_TYPES = [
    "Resource",
    "Supplier"
]

# Business objects actors may interact with
#
# Project is deliberately excluded because it is an
# umbrella object and could artificially make many events
# appear cross-object.
BUSINESS_TYPES = [
    "Requirement",
    "Asset",
    "Order",
    "Invoice",
    "AcceptanceRecord",
    "Voucher"
]


# ============================================================
# 6. CHECK WHICH OBJECT TYPES EXIST
# ============================================================

available_actor_types = [
    x for x in ACTOR_TYPES
    if x in df.columns
]

available_business_types = [
    x for x in BUSINESS_TYPES
    if x in df.columns
]

print("\n=====================================")
print("OBJECT TYPE CHECK")
print("=====================================")

print(
    "Actor types found:",
    available_actor_types
)

print(
    "Business object types found:",
    available_business_types
)


if len(available_actor_types) == 0:
    raise ValueError(
        "Neither Resource nor Supplier was found "
        "in the OCPA event table."
    )

if len(available_business_types) == 0:
    raise ValueError(
        "None of the expected business object "
        "types was found."
    )


# ============================================================
# 7. HELPER: CONVERT OCPA VALUES TO LIST
# ============================================================

def as_list(value):
    """
    OCPA object-type columns may contain:
    - set
    - list
    - tuple
    - scalar
    - NaN
    - None

    Convert everything into a Python list.
    """

    if value is None:
        return []

    if isinstance(
        value,
        (list, set, tuple)
    ):
        return list(value)

    try:
        if pd.isna(value):
            return []
    except Exception:
        pass

    return [value]


# ============================================================
# 8. IDENTIFY EVENT ID COLUMN
# ============================================================

# OCPA versions may store event_id either
# as a normal column or as index.

if "event_id" not in df.columns:

    df = df.reset_index()

    if "event_id" not in df.columns:

        first_col = df.columns[0]

        df = df.rename(
            columns={
                first_col: "event_id"
            }
        )


# Check activity column
if "event_activity" not in df.columns:
    raise ValueError(
        "event_activity column not found.\n"
        f"Available columns are:\n{df.columns.tolist()}"
    )


print("\nEvent ID column ready.")


# ============================================================
# 9. EXTRACT ACTOR × EVENT × BUSINESS OBJECT RELATIONS
# ============================================================

records = []


for _, row in df.iterrows():

    event_id = row["event_id"]
    activity = row["event_activity"]

    # Timestamp is optional
    timestamp = (
        row["event_timestamp"]
        if "event_timestamp" in df.columns
        else None
    )


    # --------------------------------------------------------
    # Actors involved in event
    # --------------------------------------------------------

    actors = []

    for actor_type in available_actor_types:

        actor_ids = as_list(
            row[actor_type]
        )

        for actor_id in actor_ids:

            actors.append(
                (
                    actor_type,
                    actor_id
                )
            )


    # --------------------------------------------------------
    # Business objects involved in event
    # --------------------------------------------------------

    business_objects = []

    for object_type in available_business_types:

        object_ids = as_list(
            row[object_type]
        )

        for object_id in object_ids:

            business_objects.append(
                (
                    object_type,
                    object_id
                )
            )


    # --------------------------------------------------------
    # Actor × business object combinations
    # --------------------------------------------------------

    for actor_type, actor_id in actors:

        for object_type, object_id in business_objects:

            records.append(
                {
                    "event_id":
                        event_id,

                    "event_timestamp":
                        timestamp,

                    "activity":
                        activity,

                    "actor_type":
                        actor_type,

                    "actor_id":
                        actor_id,

                    "business_object_type":
                        object_type,

                    "business_object_id":
                        object_id
                }
            )


interaction = pd.DataFrame(
    records
)


# ============================================================
# 10. CHECK RESULTS
# ============================================================

if interaction.empty:

    raise ValueError(
        "No actor-business-object interactions "
        "were found.\n"
        "Check the OCPA dataframe columns."
    )


print("\n=====================================")
print("01 - ACTOR × OBJECT INTERACTIONS")
print("=====================================")

print(
    "Number of actor-object relations:",
    len(interaction)
)

show(
    interaction.head(20)
)


# ============================================================
# 11. ACTOR-EVENT INTERACTION BREADTH
# ============================================================
#
# For every actor at every event:
#
# object_type_breadth
# = how many DIFFERENT business object TYPES?
#
# business_object_count
# = how many individual business OBJECTS?
#
# Example:
#
# Resource-1 participates in event e10 with:
# Requirement R1
# Asset A1
# Order O1
#
# object_type_breadth = 3
# business_object_count = 3
#
# ============================================================

actor_event_interaction = (
    interaction
    .groupby(
        [
            "actor_type",
            "actor_id",
            "event_id",
            "activity"
        ],
        dropna=False
    )
    .agg(

        object_type_breadth=(
            "business_object_type",
            "nunique"
        ),

        business_object_count=(
            "business_object_id",
            "nunique"
        )
    )
    .reset_index()
)


# ============================================================
# 12. ADD MULTI-OBJECT FLAGS
# ============================================================

# Multiple individual business objects
actor_event_interaction[
    "multi_object"
] = (
    actor_event_interaction[
        "business_object_count"
    ] >= 2
)


# Multiple different business object TYPES
actor_event_interaction[
    "cross_object_type"
] = (
    actor_event_interaction[
        "object_type_breadth"
    ] >= 2
)


print("\n=====================================")
print("02 - ACTOR-EVENT INTERACTIONS")
print("=====================================")

show(
    actor_event_interaction.head(20)
)


# ============================================================
# 13. MULTI-OBJECT EVENTS
# ============================================================
#
# Main definition used for BQ4:
#
# actor interacts with at least TWO DIFFERENT
# business object types in the same event.
#
# This is stronger than simply having two
# objects of the same type.
#
# ============================================================

multi_object_events = (
    actor_event_interaction[
        actor_event_interaction[
            "cross_object_type"
        ]
    ]
    .copy()
    .sort_values(
        [
            "object_type_breadth",
            "business_object_count"
        ],
        ascending=[
            False,
            False
        ]
    )
)


print("\n=====================================")
print("03 - MULTI-OBJECT EVENTS")
print("=====================================")

print(
    "Number of cross-object actor-events:",
    len(multi_object_events)
)

show(
    multi_object_events.head(50)
)


# ============================================================
# 14. MAIN BQ4 HOTSPOT TABLE
# ============================================================
#
# Question:
# WHICH actor
# WHERE (activity)
# HOW OFTEN
# interacts across multiple business objects?
#
# ============================================================

if not multi_object_events.empty:

    interaction_hotspots = (
        multi_object_events
        .groupby(
            [
                "actor_type",
                "actor_id",
                "activity"
            ]
        )
        .agg(

            interaction_events=(
                "event_id",
                "nunique"
            ),

            mean_object_type_breadth=(
                "object_type_breadth",
                "mean"
            ),

            max_object_type_breadth=(
                "object_type_breadth",
                "max"
            ),

            mean_object_count=(
                "business_object_count",
                "mean"
            ),

            max_object_count=(
                "business_object_count",
                "max"
            )
        )
        .reset_index()
        .sort_values(
            [
                "interaction_events",
                "mean_object_type_breadth",
                "mean_object_count"
            ],
            ascending=[
                False,
                False,
                False
            ]
        )
    )

else:

    interaction_hotspots = pd.DataFrame(
        columns=[
            "actor_type",
            "actor_id",
            "activity",
            "interaction_events",
            "mean_object_type_breadth",
            "max_object_type_breadth",
            "mean_object_count",
            "max_object_count"
        ]
    )


print("\n=====================================")
print("04 - BQ4 INTERACTION HOTSPOTS")
print("=====================================")

show(
    interaction_hotspots
)


# ============================================================
# 15. ACTOR × OBJECT TYPE SUMMARY
# ============================================================
#
# Answers:
#
# Which types of business objects does
# each Resource / Supplier interact with?
#
# ============================================================

actor_object_summary = (
    interaction
    .groupby(
        [
            "actor_type",
            "actor_id",
            "business_object_type"
        ]
    )
    .agg(

        events=(
            "event_id",
            "nunique"
        ),

        unique_objects=(
            "business_object_id",
            "nunique"
        )
    )
    .reset_index()
    .sort_values(
        [
            "actor_type",
            "actor_id",
            "events"
        ],
        ascending=[
            True,
            True,
            False
        ]
    )
)


print("\n=====================================")
print("05 - ACTOR × OBJECT TYPE SUMMARY")
print("=====================================")

show(
    actor_object_summary
)


# ============================================================
# 16. ACTOR-LEVEL OVERALL SUMMARY
# ============================================================
#
# Answers:
#
# Which actors have the broadest cross-object involvement?
#
# ============================================================

actor_overall_summary = (
    interaction
    .groupby(
        [
            "actor_type",
            "actor_id"
        ]
    )
    .agg(

        total_events=(
            "event_id",
            "nunique"
        ),

        activity_count=(
            "activity",
            "nunique"
        ),

        object_type_count=(
            "business_object_type",
            "nunique"
        ),

        unique_business_objects=(
            "business_object_id",
            "nunique"
        )
    )
    .reset_index()
)


# Number of cross-object events per actor
cross_object_actor_counts = (
    multi_object_events
    .groupby(
        [
            "actor_type",
            "actor_id"
        ]
    )
    .agg(
        cross_object_events=(
            "event_id",
            "nunique"
        )
    )
    .reset_index()
)


actor_overall_summary = (
    actor_overall_summary
    .merge(
        cross_object_actor_counts,
        on=[
            "actor_type",
            "actor_id"
        ],
        how="left"
    )
)


actor_overall_summary[
    "cross_object_events"
] = (
    actor_overall_summary[
        "cross_object_events"
    ]
    .fillna(0)
    .astype(int)
)


# Share of actor events that are cross-object
actor_overall_summary[
    "cross_object_event_share"
] = (
    actor_overall_summary[
        "cross_object_events"
    ]
    /
    actor_overall_summary[
        "total_events"
    ]
)


actor_overall_summary = (
    actor_overall_summary
    .sort_values(
        [
            "cross_object_events",
            "object_type_count",
            "unique_business_objects"
        ],
        ascending=[
            False,
            False,
            False
        ]
    )
)


print("\n=====================================")
print("06 - ACTOR OVERALL SUMMARY")
print("=====================================")

show(
    actor_overall_summary
)


# ============================================================
# 17. ACTIVITY-LEVEL HOTSPOTS
# ============================================================
#
# Answers:
#
# WHERE in the process do shared actors interact
# with multiple object types?
#
# This is particularly useful for the thesis.
#
# ============================================================

if not multi_object_events.empty:

    activity_hotspots = (
        multi_object_events
        .groupby(
            "activity"
        )
        .agg(

            multi_object_events=(
                "event_id",
                "nunique"
            ),

            actor_count=(
                "actor_id",
                "nunique"
            ),

            mean_object_type_breadth=(
                "object_type_breadth",
                "mean"
            ),

            max_object_type_breadth=(
                "object_type_breadth",
                "max"
            ),

            mean_business_object_count=(
                "business_object_count",
                "mean"
            )
        )
        .reset_index()
        .sort_values(
            [
                "multi_object_events",
                "mean_object_type_breadth"
            ],
            ascending=[
                False,
                False
            ]
        )
    )

else:

    activity_hotspots = pd.DataFrame(
        columns=[
            "activity",
            "multi_object_events",
            "actor_count",
            "mean_object_type_breadth",
            "max_object_type_breadth",
            "mean_business_object_count"
        ]
    )


print("\n=====================================")
print("07 - ACTIVITY HOTSPOTS")
print("=====================================")

show(
    activity_hotspots
)


# ============================================================
# 18. RESOURCE-ONLY HOTSPOTS
# ============================================================

resource_hotspots = (
    interaction_hotspots[
        interaction_hotspots[
            "actor_type"
        ] == "Resource"
    ]
    .copy()
)


print("\n=====================================")
print("RESOURCE HOTSPOTS")
print("=====================================")

show(
    resource_hotspots
)


# ============================================================
# 19. SUPPLIER-ONLY HOTSPOTS
# ============================================================

supplier_hotspots = (
    interaction_hotspots[
        interaction_hotspots[
            "actor_type"
        ] == "Supplier"
    ]
    .copy()
)


print("\n=====================================")
print("SUPPLIER HOTSPOTS")
print("=====================================")

show(
    supplier_hotspots
)


# ============================================================
# 20. SAVE CSV FILES
# ============================================================

results = {

    "01_actor_object_interactions":
        interaction,

    "02_actor_event_interaction":
        actor_event_interaction,

    "03_multi_object_events":
        multi_object_events,

    "04_BQ4_interaction_hotspots":
        interaction_hotspots,

    "05_actor_object_summary":
        actor_object_summary,

    "06_actor_overall_summary":
        actor_overall_summary,

    "07_activity_hotspots":
        activity_hotspots,

    "08_resource_hotspots":
        resource_hotspots,

    "09_supplier_hotspots":
        supplier_hotspots
}


for name, result_df in results.items():

    result_df.to_csv(
        os.path.join(
            OUTPUT_DIR,
            f"{name}.csv"
        ),
        index=False
    )


# ============================================================
# 21. REMOVE TIMEZONE BEFORE EXCEL
# ============================================================
#
# Excel cannot store timezone-aware datetime values.
#
# CSV keeps the original values.
# Excel receives a timezone-free copy.
#
# ============================================================

def prepare_for_excel(dataframe):

    result = dataframe.copy()

    for col in result.columns:

        if isinstance(
            result[col].dtype,
            pd.DatetimeTZDtype
        ):

            result[col] = (
                result[col]
                .dt
                .tz_localize(None)
            )

    return result


# ============================================================
# 22. SAVE EVERYTHING TO ONE EXCEL FILE
# ============================================================

excel_path = os.path.join(
    OUTPUT_DIR,
    "BQ4_OCPA_results.xlsx"
)


with pd.ExcelWriter(
    excel_path,
    engine="openpyxl"
) as writer:

    for name, result_df in results.items():

        excel_df = prepare_for_excel(
            result_df
        )

        # Excel sheet name max = 31 characters
        sheet_name = name[:31]

        excel_df.to_excel(
            writer,
            sheet_name=sheet_name,
            index=False
        )


# ============================================================
# 23. FINAL OUTPUT
# ============================================================

print("\n=====================================")
print("BQ4 OCPA ANALYSIS COMPLETED")
print("=====================================")

print("\nResults folder:")
print(
    os.path.abspath(
        OUTPUT_DIR
    )
)

print("\nMain BQ4 table:")
print(
    os.path.abspath(
        os.path.join(
            OUTPUT_DIR,
            "04_BQ4_interaction_hotspots.csv"
        )
    )
)

print("\nExcel workbook:")
print(
    os.path.abspath(
        excel_path
    )
)