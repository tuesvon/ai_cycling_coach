CYCLING_TYPES = {
    "cycling",
    "road_biking",
    "mountain_biking",
    "gravel_cycling",
    "indoor_cycling",
    "virtual_ride",
    "ebiking"
}

WALKING_TYPES = {
    "walking",
    "hiking",
    "casual_walking"
}

STRENGTH_TYPES = {
    "strength_training",
    "weight_training",
    "strength",
    "gym"
}


def classify_activity(activity):
    activity_type = activity.get("activity_type")

    if isinstance(activity_type, dict):
        type_key = activity_type.get("typeKey")
    else:
        type_key = activity_type

    type_key = str(type_key or "").lower().strip()

    if (
        type_key in CYCLING_TYPES
        or "cycling" in type_key
        or "biking" in type_key
    ):
        return "cycling"

    if (
        type_key in WALKING_TYPES
        or "walking" in type_key
        or "hiking" in type_key
    ):
        return "walking"

    if (
        type_key in STRENGTH_TYPES
        or "strength" in type_key
        or "weight_training" in type_key
    ):
        return "strength"

    return "other"