from datetime import timedelta
from statistics import mean, median

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    extract_record_window,
    calculate_window_metrics,
    calculate_difference,
    get_valid_field,
)


SUPPORTED_RIDING_MODES = {
    "erg",
    "simulation",
    "free_ride",
    "race",
    "unknown",
}

BASELINE_SECONDS = 30

POST_EVENT_SECONDS = 60

MIN_BASELINE_COVERAGE = 0.90

MIN_HEART_RATE_COVERAGE = 0.90

MIN_CADENCE_COVERAGE = 0.90

BRIEF_COASTING_SECONDS = 5

MAX_SHORT_COASTING_SECONDS = 15

POSSIBLE_STOP_SECONDS = 60

POWER_SPIKE_SECONDS = 3

MIN_SURGE_POWER_INCREASE_WATTS = 50

MIN_SURGE_POWER_RATIO = 1.30

SURGE_END_POWER_RATIO = 1.15

MIN_SURGE_BASELINE_FTP_RATIO = 0.30

HEART_RATE_CHANGE_THRESHOLD = 5

PEDALING_CADENCE_THRESHOLD = 20

MIN_ERG_TRANSITION_SECONDS = 30

MAX_BASELINE_POWER_CV_PERCENT = 10


def normalize_riding_mode(riding_mode):
    """
    Проверяет переданный режим езды.

    Не определяет ERG автоматически
    по названию активности.
    """
    if riding_mode is None:
        return "unknown"

    if not isinstance(riding_mode, str):
        raise ValueError(
            "Режим езды должен быть строкой"
        )

    normalized = riding_mode.strip().lower()

    if normalized not in SUPPORTED_RIDING_MODES:
        raise ValueError(
            f"Неизвестный режим езды: {normalized}"
        )

    return normalized


def get_record_power(record):
    return get_valid_field(
        record,
        "power",
    )


def calculate_power_baseline(
    indexed_records,
    event_start,
):
    """
    Определяет базовую мощность
    за 30 секунд перед событием.

    Использует медиану для уменьшения
    влияния отдельных скачков.
    """
    from statistics import pstdev

    window = extract_record_window(
        indexed_records=indexed_records,
        start=(
            event_start
            - timedelta(seconds=BASELINE_SECONDS)
        ),
        duration_seconds=BASELINE_SECONDS,
    )

    powers = [
        get_record_power(record)
        for record in window
    ]

    valid_powers = [
        power
        for power in powers
        if power is not None
    ]

    coverage = (
        len(valid_powers)
        / BASELINE_SECONDS
    )

    result = {
        "status": "insufficient_data",
        "median_power": None,
        "average_power": None,
        "power_cv_percent": None,
        "coverage_ratio": round(coverage, 4),
        "stable": False,
    }

    if coverage < MIN_BASELINE_COVERAGE:
        return result

    average_power = mean(valid_powers)

    power_cv = None

    if average_power > 0:
        power_cv = (
            pstdev(valid_powers)
            / average_power
            * 100
        )

    return {
        **result,

        "status": "ok",

        "median_power": round(
            median(valid_powers), 2
        ),

        "average_power": round(
            average_power, 2
        ),

        "power_cv_percent": (
            round(power_cv, 2)
            if power_cv is not None
            else None
        ),

        "stable": (
            power_cv is not None
            and power_cv <= MAX_BASELINE_POWER_CV_PERCENT
            and coverage == 1.0
        ),
    }


def analyze_event_context(
    indexed_records,
    event_start,
    event_end,
):
    """
    Анализирует показатели до события,
    во время него и после завершения.
    """
    duration = int(
        (event_end - event_start).total_seconds()
    ) + 1

    before_window = extract_record_window(
        indexed_records=indexed_records,

        start=(
            event_start
            - timedelta(seconds=BASELINE_SECONDS)
        ),

        duration_seconds=BASELINE_SECONDS,
    )

    event_window = extract_record_window(
        indexed_records=indexed_records,
        start=event_start,
        duration_seconds=duration,
    )

    after_window = extract_record_window(
        indexed_records=indexed_records,

        start=(
            event_end
            + timedelta(seconds=1)
        ),

        duration_seconds=POST_EVENT_SECONDS,
    )

    before = calculate_window_metrics(
        before_window
    )

    during = calculate_window_metrics(
        event_window
    )

    after = calculate_window_metrics(
        after_window
    )

    before_hr = None

    if (
        before["heart_rate_coverage_ratio"]
        >= MIN_HEART_RATE_COVERAGE
    ):
        before_hr = before[
            "average_heart_rate"
        ]

    after_peak_hr = None

    if (
        after["heart_rate_coverage_ratio"]
        >= MIN_HEART_RATE_COVERAGE
    ):
        after_peak_hr = after[
            "max_heart_rate"
        ]

    event_peak_hr = None

    if (
        during["heart_rate_coverage_ratio"]
        >= MIN_HEART_RATE_COVERAGE
    ):
        event_peak_hr = during[
            "max_heart_rate"
        ]

    peak_values = [
        value

        for value in (
            event_peak_hr,
            after_peak_hr,
        )

        if is_valid_number(value)
    ]

    observed_peak_hr = (
        max(peak_values)
        if peak_values
        else None
    )

    after_hr = None

    if (
        after["heart_rate_coverage_ratio"]
        >= MIN_HEART_RATE_COVERAGE
    ):
        after_hr = after[
            "average_heart_rate"
        ]

    hr_peak_increase = calculate_difference(
        observed_peak_hr,
        before_hr,
    )

    hr_after_difference = calculate_difference(
        after_hr,
        before_hr,
    )

    cadence_before = before[
        "average_cadence"
    ]

    cadence_during = during[
        "average_cadence"
    ]

    if (
        before["cadence_coverage_ratio"]
        < MIN_CADENCE_COVERAGE
    ):
        cadence_before = None

    if (
        during["cadence_coverage_ratio"]
        < MIN_CADENCE_COVERAGE
    ):
        cadence_during = None

    return {
        "before_event": before,

        "during_event": during,

        "after_event": after,

        "heart_rate_response": {
            "baseline_heart_rate": before_hr,

            "observed_peak_heart_rate": (
                observed_peak_hr
            ),

            "peak_increase_bpm": (
                hr_peak_increase
            ),

            "after_event_difference_bpm": (
                hr_after_difference
            ),

            "possible_delayed_response": (
                event_peak_hr is not None
                and after_peak_hr is not None
                and after_peak_hr > event_peak_hr
            ),
        },

        "cadence_response": {
            "before_event_rpm": (
                cadence_before
            ),

            "during_event_rpm": (
                cadence_during
            ),

            "difference_rpm": (
                calculate_difference(
                    cadence_during,
                    cadence_before,
                )
            ),
        },

        "limitations": [
            (
                "Последующее изменение ЧСС "
                "может быть вызвано другими "
                "событиями внутри окна наблюдения"
            ),
        ],
    }


def classify_zero_power_event(
    duration_seconds,
    context,
):
    """
    Классифицирует участок нулевой мощности.

    Не использует нулевую мощность
    как доказательство остановки велосипеда.
    """
    cadence = context[
        "cadence_response"
    ]["during_event_rpm"]

    hr_difference = context[
        "heart_rate_response"
    ]["after_event_difference_bpm"]

    limitations = []

    if cadence is None:
        return {
            "event_type": "zero_power_unknown",

            "confidence": "low",

            "possible_causes": [
                "coasting",
                "stop",
                "power_sensor_issue",
            ],

            "limitations": [
                "missing_cadence",
            ],
        }

    if cadence >= PEDALING_CADENCE_THRESHOLD:
        return {
            "event_type": "possible_power_dropout",

            "confidence": "medium",

            "possible_causes": [
                "power_sensor_issue",
                "unloaded_pedaling",
                "device_reporting_behavior",
            ],

            "limitations": [
                "zero_power_with_nonzero_cadence",
            ],
        }

    if cadence > 0:
        return {
            "event_type": "zero_power_unknown",

            "confidence": "low",

            "possible_causes": [
                "very_slow_pedaling",
                "coasting",
                "sensor_reporting_delay",
            ],

            "limitations": [
                "low_nonzero_cadence",
            ],
        }

    if hr_difference is None:
        limitations.append(
            "missing_heart_rate_context"
        )

    if duration_seconds <= BRIEF_COASTING_SECONDS:
        event_type = "brief_coasting"

    elif (
        duration_seconds >= POSSIBLE_STOP_SECONDS

        and hr_difference is not None

        and hr_difference
        <= -HEART_RATE_CHANGE_THRESHOLD
    ):
        event_type = "possible_stop"

    else:
        event_type = "extended_coasting"

    return {
        "event_type": event_type,

        "confidence": (
            "medium"
            if not limitations
            else "low"
        ),

        "possible_causes": [
            "coasting",
            "brief_pause",
            "stop",
        ],

        "limitations": limitations,
    }


def classify_power_surge(
    duration_seconds,
    context,
    riding_mode,
):
    """
    Классифицирует выраженное
    увеличение мощности.

    Не утверждает, что спортсмен
    ускорился намеренно.
    """
    heart_rate_response = context[
        "heart_rate_response"
    ]

    cadence_response = context[
        "cadence_response"
    ]

    hr_increase = heart_rate_response[
        "peak_increase_bpm"
    ]

    cadence_difference = cadence_response[
        "difference_rpm"
    ]

    limitations = [
        "planned_target_unknown",
    ]

    hr_response_detected = (
        hr_increase is not None
        and hr_increase >= HEART_RATE_CHANGE_THRESHOLD
    )

    if hr_increase is None:
        limitations.append(
            "missing_heart_rate_context"
        )

    if (
        duration_seconds <= POWER_SPIKE_SECONDS
        and not hr_response_detected
    ):
        return {
            "event_type": "possible_power_spike",

            "confidence": "low",

            "possible_causes": [
                "short_physical_effort",
                "power_sensor_spike",
                "trainer_transient",
            ],

            "limitations": limitations,
        }

    if (
        riding_mode == "erg"

        and duration_seconds
        >= MIN_ERG_TRANSITION_SECONDS
    ):
        return {
            "event_type": "possible_erg_transition",

            "confidence": "low",

            "possible_causes": [
                "planned_power_target_change",
                "trainer_resistance_change",
                "intentional_acceleration",
            ],

            "limitations": limitations,
        }

    possible_causes = [
        "physical_effort",
        "planned_interval",
        "unplanned_acceleration",
    ]

    if riding_mode == "erg":
        possible_causes.append(
            "trainer_resistance_transient"
        )

        if (
            cadence_difference is not None
            and cadence_difference < -10
        ):
            limitations.append(
                "cadence_decreased_during_surge"
            )

    return {
        "event_type": "power_surge",

        "confidence": (
            "medium"
            if hr_response_detected
            else "low"
        ),

        "possible_causes": possible_causes,

        "limitations": limitations,
    }


def get_event_handling_recommendation(
    event_type,
    duration_seconds,
    context,
):
    """
    Определяет предварительную рекомендацию
    для последующих аналитических модулей.

    Исходные FIT-записи не изменяются.
    """
    result = {
        "preserve_raw_records": True,

        "interpolate_missing_data": False,

        "aerobic_segment_action": "review",

        "recovery_window_action": "review",
    }

    if event_type == "brief_coasting":
        return {
            **result,

            "aerobic_segment_action": (
                "bridge_candidate"
            ),

            "recovery_window_action": (
                "retain_with_annotation"
            ),
        }

    if event_type == "extended_coasting":
        if duration_seconds <= MAX_SHORT_COASTING_SECONDS:
            action = "review"

        else:
            action = "split"

        return {
            **result,

            "aerobic_segment_action": action,
        }

    if event_type in {
        "time_gap",
        "power_data_gap",
        "possible_stop",
        "power_surge",
        "possible_erg_transition",
    }:
        return {
            **result,

            "aerobic_segment_action": "split",

            "recovery_window_action": (
                "reassess_or_truncate"
            ),
        }

    if event_type in {
        "possible_power_dropout",
        "possible_power_spike",
        "zero_power_unknown",
    }:
        return {
            **result,

            "aerobic_segment_action": (
                "exclude_or_split"
            ),

            "recovery_window_action": (
                "reassess_or_truncate"
            ),
        }

    return result


def build_power_event(
    indexed_records,
    event_start,
    event_end,
    raw_event_type,
    riding_mode,
    ftp=None,
    baseline=None,
):
    """
    Формирует единое описание события.
    """
    duration = int(
        (event_end - event_start).total_seconds()
    ) + 1

    context = analyze_event_context(
        indexed_records=indexed_records,
        event_start=event_start,
        event_end=event_end,
    )

    if baseline is None:
        baseline = calculate_power_baseline(
            indexed_records,
            event_start,
        )

    if raw_event_type == "zero_power":
        classification = classify_zero_power_event(
            duration_seconds=duration,
            context=context,
        )

    elif raw_event_type == "surge":
        classification = classify_power_surge(
            duration_seconds=duration,
            context=context,
            riding_mode=riding_mode,
        )

    else:
        classification = {
            "event_type": raw_event_type,

            "confidence": "high",

            "possible_causes": [
                "missing_measurement",
                "recording_interruption",
            ],

            "limitations": [],
        }

    metrics = context[
        "during_event"
    ]

    average_power = metrics[
        "average_power"
    ]

    max_power = None

    event_window = extract_record_window(
        indexed_records=indexed_records,
        start=event_start,
        duration_seconds=duration,
    )

    powers = [
        get_record_power(record)
        for record in event_window
    ]

    valid_powers = [
        power
        for power in powers
        if power is not None
    ]

    if valid_powers:
        max_power = max(valid_powers)

    additional_work_kj = None

    baseline_power = baseline[
        "median_power"
    ]

    if (
        raw_event_type == "surge"

        and baseline.get("stable") is True

        and baseline_power is not None

        and len(valid_powers) == duration
    ):
        additional_work_kj = round(
            sum(
                max(0, power - baseline_power)

                for power in valid_powers
            ) / 1000,
            2,
        )

    handling = get_event_handling_recommendation(
        event_type=classification["event_type"],

        duration_seconds=duration,

        context=context,
    )

    return {
        "raw_event_type": raw_event_type,

        **classification,

        "start": event_start.isoformat(),

        "end": event_end.isoformat(),

        "duration_seconds": duration,

        "riding_mode": riding_mode,

        "average_power": average_power,

        "max_power": max_power,

        "average_power_ftp_percent": (
            round(average_power / ftp * 100, 2)

            if average_power is not None
            and ftp is not None

            else None
        ),

        "power_difference_from_baseline": (
            calculate_difference(
                average_power,
                baseline_power,
            )
        ),

        "additional_work_kj": additional_work_kj,

        "baseline": baseline,

        "context": context,

        "handling": handling,
    }


def detect_power_events(
    records,
    ftp=None,
    riding_mode="unknown",
    ignore_heart_rate=False,
):
    """
    Обнаруживает отклонения мощности
    в исходных FIT-записях.

    Поддерживает разные режимы езды.

    Не изменяет исходные записи,
    не интерполирует пропуски
    и не определяет намерения спортсмена.
    """
    if not isinstance(records, list):
        raise ValueError(
            "FIT-записи должны быть списком"
        )

    if not isinstance(ignore_heart_rate, bool):
        raise ValueError(
            "ignore_heart_rate должен быть bool"
        )

    if ftp is not None:
        if not is_valid_number(ftp) or ftp <= 0:
            raise ValueError(
                "Некорректный FTP"
            )

    riding_mode = normalize_riding_mode(
        riding_mode
    )

    prepared_records = []

    for record in records:
        if not isinstance(record, dict):
            continue

        copied = dict(record)

        if ignore_heart_rate:
            copied.pop("heart_rate", None)

        prepared_records.append(copied)

    indexed = prepare_effort_records(
        prepared_records
    )

    timestamps = sorted(indexed)

    events = []

    if not timestamps:
        return {
            "status": "insufficient_data",

            "events": [],

            "statistics": {
                "events_count": 0,
            },
        }

    # Сначала обнаруживаем разрывы времени.
    # Отсутствующие секунды не считаются
    # нулевой мощностью.

    for previous, current in zip(
        timestamps,
        timestamps[1:],
    ):
        difference = (
            current - previous
        ).total_seconds()

        if difference == 1:
            continue

        if difference > 1 and difference.is_integer():
            missing_seconds = int(difference) - 1

            events.append({
                "raw_event_type": "time_gap",

                "event_type": "time_gap",

                "confidence": "high",

                "start": (
                    previous + timedelta(seconds=1)
                ).isoformat(),

                "end": (
                    current - timedelta(seconds=1)
                ).isoformat(),

                "duration_seconds": missing_seconds,

                "riding_mode": riding_mode,

                "possible_causes": [
                    "recording_interruption",
                    "missing_or_duplicate_records",
                ],

                "limitations": [],

                "handling": (
                    get_event_handling_recommendation(
                        event_type="time_gap",
                        duration_seconds=missing_seconds,
                        context={},
                    )
                ),
            })

        else:
            events.append({
                "raw_event_type": "time_gap",

                "event_type": "time_gap",

                "confidence": "high",

                "start": previous.isoformat(),

                "end": current.isoformat(),

                "duration_seconds": None,

                "timestamp_interval_seconds": difference,

                "riding_mode": riding_mode,

                "possible_causes": [
                    "irregular_sampling",
                ],

                "limitations": [
                    "non_one_second_sampling",
                ],

                "handling": (
                    get_event_handling_recommendation(
                        event_type="time_gap",
                        duration_seconds=None,
                        context={},
                    )
                ),
            })

    index = 0

    while index < len(timestamps):
        timestamp = timestamps[index]

        record = indexed[timestamp]

        power = get_record_power(record)

        raw_event_type = None

        baseline = None

        surge_end_threshold = None

        if power is None:
            raw_event_type = "power_data_gap"

        elif power == 0:
            raw_event_type = "zero_power"

        else:
            baseline = calculate_power_baseline(
                indexed_records=indexed,

                event_start=timestamp,
            )

            baseline_power = baseline[
                "median_power"
            ]

            minimum_baseline = (
                ftp * MIN_SURGE_BASELINE_FTP_RATIO

                if ftp is not None

                else 50
            )

            if (
                baseline.get("stable") is True

                and baseline_power is not None

                and baseline_power >= minimum_baseline
            ):
                surge_start_threshold = max(
                    baseline_power
                    * MIN_SURGE_POWER_RATIO,

                    baseline_power
                    + MIN_SURGE_POWER_INCREASE_WATTS,
                )

                if power >= surge_start_threshold:
                    raw_event_type = "surge"

                    surge_end_threshold = (
                        baseline_power
                        * SURGE_END_POWER_RATIO
                    )

        if raw_event_type is None:
            index += 1
            continue

        event_start = timestamp

        end_index = index

        while end_index + 1 < len(timestamps):
            current_timestamp = timestamps[
                end_index
            ]

            next_timestamp = timestamps[
                end_index + 1
            ]

            difference = (
                next_timestamp - current_timestamp
            ).total_seconds()

            if difference != 1:
                break

            next_power = get_record_power(
                indexed[next_timestamp]
            )

            if raw_event_type == "power_data_gap":
                continues = next_power is None

            elif raw_event_type == "zero_power":
                continues = next_power == 0

            else:
                continues = (
                    next_power is not None

                    and next_power
                    >= surge_end_threshold
                )

            if not continues:
                break

            end_index += 1

        event_end = timestamps[
            end_index
        ]

        event = build_power_event(
            indexed_records=indexed,

            event_start=event_start,

            event_end=event_end,

            raw_event_type=raw_event_type,

            riding_mode=riding_mode,

            ftp=ftp,

            baseline=baseline,
        )

        events.append(event)

        index = end_index + 1

    events.sort(
        key=lambda event: event["start"]
    )

    event_counts = {}

    for number, event in enumerate(
        events,
        start=1,
    ):
        event["event_id"] = (
            f"power_event_{number}"
        )

        event_type = event[
            "event_type"
        ]

        event_counts[event_type] = (
            event_counts.get(event_type, 0)
            + 1
        )

    bridge_candidates_count = sum(
        event["handling"][
            "aerobic_segment_action"
        ] == "bridge_candidate"

        for event in events
    )

    return {
        "status": "ok",

        "riding_mode": riding_mode,

        "ftp": ftp,

        "ignore_heart_rate": ignore_heart_rate,

        "events": events,

        "statistics": {
            "events_count": len(events),

            "event_type_counts": event_counts,

            "bridge_candidates_count": (
                bridge_candidates_count
            ),

            "indexed_records_count": len(indexed),

            "input_records_count": len(records),
        },

        "limitations": [
            (
                "Режим езды передаётся извне "
                "и не определяется автоматически"
            ),
            (
                "Намерение спортсмена невозможно "
                "достоверно определить только по FIT"
            ),
            (
                "Плановые изменения мощности "
                "могут обнаруживаться как ускорения"
            ),
            (
                "Нулевая мощность не равнозначна "
                "отсутствующим измерениям"
            ),
            (
                "Кратковременные отклонения "
                "не удаляются из исходных данных"
            ),
            (
                "Рекомендация bridge_candidate "
                "не гарантирует возможность "
                "объединения аэробных участков"
            ),
            (
                "Пульс после события может отражать "
                "влияние последующих усилий"
            ),
        ],
    }