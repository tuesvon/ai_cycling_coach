from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_detection import (
    detect_workout_efforts,
    EFFORT_PROFILES,
)


PROFILE_PRIORITY = {
    name: index
    for index, name in enumerate(
        EFFORT_PROFILES
    )
}


def get_effort_bounds(effort):
    """
    Возвращает временные границы усилия.
    """
    start = parse_activity_date(
        effort["start"]
    )

    end = parse_activity_date(
        effort["end"]
    )

    if end < start:
        raise ValueError(
            "Некорректные границы усилия"
        )

    return start, end


def collect_unique_efforts(
    efforts_by_type,
):
    """
    Объединяет описания усилий
    с одинаковыми временными границами.

    Все исходные профили сохраняются.
    """
    grouped = {}

    for profile, efforts in (
        efforts_by_type.items()
    ):
        for effort in efforts:
            start, end = get_effort_bounds(
                effort
            )

            key = (start, end)

            if key not in grouped:
                grouped[key] = []

            grouped[key].append({
                "profile": profile,
                "effort": dict(effort),
            })

    unique_efforts = []

    sorted_groups = sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0],
            -item[0][1].timestamp(),
        ),
    )

    for index, (bounds, entries) in enumerate(
        sorted_groups,
        start=1,
    ):
        start, end = bounds

        profiles = sorted(
            {
                entry["profile"]
                for entry in entries
            },
            key=lambda profile: (
                PROFILE_PRIORITY[profile]
            ),
        )

        primary_profile = profiles[-1]

        primary_effort = next(
            entry["effort"]
            for entry in entries
            if entry["profile"]
            == primary_profile
        )

        unique_efforts.append({
            **primary_effort,

            "effort_id": f"effort_{index}",

            "start": start.isoformat(),

            "end": end.isoformat(),

            "primary_profile": (
                primary_profile
            ),

            "matched_profiles": profiles,

            "source_efforts_count": len(
                entries
            ),

            "source_efforts": entries,

            "parent_effort_id": None,

            "child_effort_ids": [],

            "overlapping_effort_ids": [],
        })

    return unique_efforts


def assign_effort_relationships(
    efforts,
):
    """
    Определяет вложенность и частичные
    пересечения усилий.

    При нескольких возможных родителях
    выбирается самый короткий
    содержащий участок.
    """
    bounds = {
        effort["effort_id"]: (
            get_effort_bounds(effort)
        )
        for effort in efforts
    }

    efforts_by_id = {
        effort["effort_id"]: effort
        for effort in efforts
    }

    for effort in efforts:
        effort["parent_effort_id"] = None
        effort["child_effort_ids"] = []
        effort["overlapping_effort_ids"] = []

    for effort in efforts:
        effort_id = effort["effort_id"]

        start, end = bounds[effort_id]

        possible_parents = []

        for candidate in efforts:
            candidate_id = candidate[
                "effort_id"
            ]

            if candidate_id == effort_id:
                continue

            candidate_start, candidate_end = (
                bounds[candidate_id]
            )

            contains_effort = (
                candidate_start <= start
                and candidate_end >= end
                and (
                    candidate_start < start
                    or candidate_end > end
                )
            )

            if contains_effort:
                possible_parents.append(
                    candidate
                )

            else:
                overlaps = (
                    candidate_start <= end
                    and candidate_end >= start
                )

                contained_by_effort = (
                    start <= candidate_start
                    and end >= candidate_end
                )

                if (
                    overlaps
                    and not contained_by_effort
                ):
                    effort[
                        "overlapping_effort_ids"
                    ].append(candidate_id)

        if possible_parents:
            parent = min(
                possible_parents,
                key=lambda item: (
                    item["duration_seconds"]
                ),
            )

            parent_id = parent["effort_id"]

            effort["parent_effort_id"] = (
                parent_id
            )

            efforts_by_id[parent_id][
                "child_effort_ids"
            ].append(effort_id)

    return efforts


def calculate_unique_effort_seconds(
    efforts,
):
    """
    Рассчитывает продолжительность
    объединения временных диапазонов.

    Пересекающиеся секунды учитываются
    только один раз.
    """
    if not efforts:
        return 0

    ranges = sorted(
        get_effort_bounds(effort)
        for effort in efforts
    )

    current_start, current_end = ranges[0]

    total_seconds = 0

    for start, end in ranges[1:]:
        if start <= current_end:
            current_end = max(
                current_end,
                end,
            )

        else:
            total_seconds += int(
                (
                    current_end
                    - current_start
                ).total_seconds()
            ) + 1

            current_start = start
            current_end = end

    total_seconds += int(
        (
            current_end
            - current_start
        ).total_seconds()
    ) + 1

    return total_seconds


def resolve_detected_efforts(
    detection_result,
):
    """
    Формирует единую структуру
    ранее обнаруженных усилий.

    Исходные усилия остаются доступными.
    """
    if not isinstance(
        detection_result,
        dict,
    ):
        raise ValueError(
            "Результат обнаружения "
            "должен быть словарём"
        )

    if detection_result.get("status") != "ok":
        return {
            "status": "insufficient_data",

            "reason": detection_result.get(
                "reason"
            ),

            "efforts": [],

            "root_effort_ids": [],

            "summary": {},
        }

    efforts_by_type = detection_result[
        "efforts_by_type"
    ]

    source_efforts = [
        effort
        for efforts in efforts_by_type.values()
        for effort in efforts
    ]

    unique_efforts = collect_unique_efforts(
        efforts_by_type
    )

    unique_efforts = (
        assign_effort_relationships(
            unique_efforts
        )
    )

    root_efforts = [
        effort
        for effort in unique_efforts
        if effort["parent_effort_id"] is None
    ]

    nested_efforts = [
        effort
        for effort in unique_efforts
        if effort["parent_effort_id"] is not None
    ]

    overlapping_efforts = [
        effort
        for effort in unique_efforts
        if effort["overlapping_effort_ids"]
    ]

    source_duration = sum(
        effort["duration_seconds"]
        for effort in source_efforts
    )

    unique_duration = (
        calculate_unique_effort_seconds(
            unique_efforts
        )
    )

    return {
        "status": "ok",

        "efforts": unique_efforts,

        "root_effort_ids": [
            effort["effort_id"]
            for effort in root_efforts
        ],

        "summary": {
            "source_efforts_count": len(
                source_efforts
            ),

            "unique_efforts_count": len(
                unique_efforts
            ),

            "duplicate_descriptions_removed": (
                len(source_efforts)
                - len(unique_efforts)
            ),

            "root_efforts_count": len(
                root_efforts
            ),

            "nested_efforts_count": len(
                nested_efforts
            ),

            "partially_overlapping_efforts_count": (
                len(overlapping_efforts)
            ),

            "source_duration_seconds": (
                source_duration
            ),

            "unique_work_seconds": (
                unique_duration
            ),

            "double_counted_seconds_removed": (
                source_duration
                - unique_duration
            ),
        },

        "limitations": [
            (
                "Основной профиль обозначает "
                "наибольший обнаруженный порог, "
                "а не физиологическую цель"
            ),
            (
                "Вложенные усилия сохраняются"
            ),
            (
                "Частичные пересечения "
                "не удаляются автоматически"
            ),
            (
                "Уникальное время работы "
                "не равно времени выше "
                "конкретного порога мощности"
            ),
            (
                "Корневое усилие не обязательно "
                "является полноценным "
                "тренировочным блоком"
            ),
        ],
    }


def analyze_resolved_workout_efforts(
    records,
    ftp,
):
    """
    Обнаруживает усилия и разрешает
    пересечения между ними.
    """
    detection = detect_workout_efforts(
        records=records,
        ftp=ftp,
    )

    resolution = resolve_detected_efforts(
        detection
    )

    return {
        **resolution,

        "original_detection": detection,
    }