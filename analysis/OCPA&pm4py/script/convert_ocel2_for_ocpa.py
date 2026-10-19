import argparse
import json
from pathlib import Path


CORE_TYPES = {
    "Requirement",
    "Asset",
    "Order",
    "Invoice",
    "AcceptanceRecord",
    "Voucher",
}


def attribute_map(attributes):
    """Convert OCEL 2.0 attribute arrays to JSONOCEL 1.0 mappings."""
    result = {}

    # If attributes change over time, the last value is retained.
    for attribute in sorted(
        attributes or [],
        key=lambda item: item.get("time", "")
    ):
        result[attribute["name"]] = attribute.get("value")

    return result


def convert(source_file, target_file, use_all_types=False):
    with open(source_file, "r", encoding="utf-8") as file:
        source = json.load(file)

    object_type = {
        obj["id"]: obj["type"]
        for obj in source["objects"]
    }

    if use_all_types:
        selected_types = set(object_type.values())
    else:
        selected_types = CORE_TYPES

    selected_object_ids = {
        object_id
        for object_id, type_name in object_type.items()
        if type_name in selected_types
    }

    objects = {}

    for obj in source["objects"]:
        if obj["id"] not in selected_object_ids:
            continue

        objects[obj["id"]] = {
            "ocel:type": obj["type"],
            "ocel:ovmap": attribute_map(obj.get("attributes", [])),
        }

    events = {}
    event_attribute_names = set()
    retained_e2o = 0

    for event in source["events"]:
        object_ids = [
            relation["objectId"]
            for relation in event.get("relationships", [])
            if relation["objectId"] in selected_object_ids
        ]

        # Remove duplicates while retaining order.
        object_ids = list(dict.fromkeys(object_ids))

        if not object_ids:
            continue

        event_attributes = attribute_map(event.get("attributes", []))
        event_attribute_names.update(event_attributes)

        events[event["id"]] = {
            "ocel:activity": event["type"],
            "ocel:timestamp": event["time"],
            "ocel:omap": object_ids,
            "ocel:vmap": event_attributes,
        }

        retained_e2o += len(object_ids)

    converted = {
        "ocel:global-log": {
            "ocel:attribute-names": sorted(event_attribute_names),
            "ocel:object-types": sorted(selected_types),
            "ocel:version": "1.0",
            "ocel:ordering": "timestamp",
        },
        "ocel:global-event": {
            "ocel:activity": "__INVALID__",
            "ocel:timestamp": "1970-01-01T00:00:00Z",
        },
        "ocel:global-object": {
            "ocel:type": "__INVALID__",
        },
        "ocel:events": events,
        "ocel:objects": objects,
    }

    with open(target_file, "w", encoding="utf-8") as file:
        json.dump(converted, file, indent=2, ensure_ascii=False)

    print(f"Output: {target_file}")
    print(f"Object types: {len(selected_types)}")
    print(f"Objects: {len(objects)}")
    print(f"Events: {len(events)}")
    print(f"Retained E2O relations: {retained_e2o}")
    print("O2O relations and qualifiers are not included in this view.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument(
        "--all-types",
        action="store_true",
        help="Retain all nine object types.",
    )
    arguments = parser.parse_args()

    convert(
        Path(arguments.source),
        Path(arguments.target),
        use_all_types=arguments.all_types,
    )