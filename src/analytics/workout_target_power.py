from collections import Counter
from datetime import timedelta
from statistics import mean

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    get_valid_field,
)


MIN_POSITIVE_TARGET_COVERAGE = 0.90

MIN_TARGET_POWER_COVERAGE = 0.90

MIN_TARGET_RECORDS = 60

TARGET_TOLERANCE_RATIO = 0.10

TARGET_TOLERANCE_WATTS = 10

SIGNIFICANT_DEVIATION_RATIO = 0.30

SIGNIFICANT_DEVIATION_WATTS = 50


def get_valid_target_power(record):
    """
    Возвращает корректное значение
    записанной целевой мощности.

    Нулевая цель сохраняется,
    но не интерпретируется автоматически
    как запланированный отдых.
    """
    return get_valid_field(
        record,
        "target_power",
    )


def assess_target_power_availability(
    records,
):
    """
    Оценивает доступность и информативность
    записанной целевой мощности.

    Не подтверждает режим ERG.
    Не использует ЧСС или успешность
    выполнения задания.
    """
    indexed = prepare_effort_records(
        records
    )

    values = [
        get_valid_target_power(record)

        for record in indexed.values()
    ]

    total = len(values)

    valid = [
        value
        for value in values
        if value is not None
    ]

    positive = [
        value
        for value in valid
        if value > 0
    ]

    zero_count = sum(
        value == 0
        for value in valid
    )

    valid_coverage = (
        len(valid) / total
        if total
        else 0.0
    )

    positive_coverage = (
        len(positive) / total
        if total
        else 0.0
    )

    reasons = []

    if total < MIN_TARGET_RECORDS:
        reasons.append(
            "insufficient_records"
        )

    if valid_coverage < MIN_TARGET_POWER_COVERAGE:
        reasons.append(
            "insufficient_target_coverage"
        )

    if not positive:
        reasons.append(
            "no_positive_target_power"
        )

    elif positive_coverage < MIN_POSITIVE_TARGET_COVERAGE:
        reasons.append(
            "insufficient_positive_target_coverage"
        )

    if total < MIN_TARGET_RECORDS:
        status = "insufficient_data"

    elif not positive:
        status = "unavailable"

    elif reasons:
        status = "partial"

    else:
        status = "available"

    return {
        "status": status,

        "usable_for_target_analysis": (
            status == "available"
        ),

        "source": "fit.record.target_power",

        "records_count": total,

        "valid_target_records": len(valid),

        "positive_target_records": len(
            positive
        ),

        "zero_target_records": zero_count,

        "missing_target_records": (
            total - len(valid)
        ),

        "valid_target_coverage_ratio": round(
            valid_coverage,
            4,
        ),

        "positive_target_coverage_ratio": round(
            positive_coverage,
            4,
        ),

        "minimum_positive_target": (
            min(positive)
            if positive
            else None
        ),

        "maximum_positive_target": (
            max(positive)
            if positive
            else None
        ),

        "unique_positive_targets": len(
            set(positive)
        ),

        "reasons": reasons,

        "limitations": [
            (
                "Информативная целевая мощность "
                "не подтверждает использование ERG"
            ),
            (
                "Покрытие рассчитано по имеющимся "
                "уникальным записям, а не по всему "
                "прошедшему времени тренировки"
            ),
            (
                "Нулевая цель может означать "
                "отсутствие задания"
            ),
            (
                "Записанная цель может отличаться "
                "от первоначального плана тренировки"
            ),
        ],
    }


def classify_target_deviation(
    actual_power,
    target_power,
):
    """
    Классифицирует одну секунду
    фактической нагрузки.

    Нулевое задание не используется
    для расчёта относительной ошибки.
    """
    if (
        not is_valid_number(target_power)
        or target_power <= 0
    ):
        return "target_unavailable"

    if (
        not is_valid_number(actual_power)
        or actual_power < 0
    ):
        return "missing_actual_power"

    if actual_power == 0:
        return "zero_power_with_target"

    difference = (
        actual_power - target_power
    )

    tolerance = max(
        TARGET_TOLERANCE_WATTS,
        target_power * TARGET_TOLERANCE_RATIO,
    )

    significant_threshold = max(
        SIGNIFICANT_DEVIATION_WATTS,
        target_power
        * SIGNIFICANT_DEVIATION_RATIO,
    )

    if abs(difference) <= tolerance:
        return "within_target"

    if difference >= significant_threshold:
        return "significantly_above_target"

    if difference <= -significant_threshold:
        return "significantly_below_target"

    if difference > 0:
        return "above_target"

    return "below_target"


def calculate_target_execution_metrics(
    records,
):
    """
    Рассчитывает соответствие фактической
    мощности записанной цели.

    Отсутствующие измерения не заменяются
    нулями.

    Нулевая фактическая мощность
    при положительной цели включается
    в расчёт выполнения задания.
    """
    counts = Counter()

    actual_values = []
    target_values = []

    differences = []
    relative_errors = []

    positive_target_seconds = 0

    above_target_work = 0.0

    below_target_work = 0.0

    for record in records:
        target = get_valid_target_power(
            record
        )

        actual = get_valid_field(
            record,
            "power",
        )

        classification = (
            classify_target_deviation(
                actual_power=actual,
                target_power=target,
            )
        )

        counts[classification] += 1

        if target is None or target <= 0:
            continue

        positive_target_seconds += 1

        if actual is None:
            continue

        difference = actual - target

        actual_values.append(actual)

        target_values.append(target)

        differences.append(difference)

        relative_errors.append(
            abs(difference) / target
        )

        above_target_work += max(
            0,
            difference,
        )

        below_target_work += max(
            0,
            -difference,
        )

    compared = len(differences)

    coverage = (
        compared / positive_target_seconds
        if positive_target_seconds
        else 0.0
    )

    result = {
        "status": "insufficient_data",

        "records_count": len(records),

        "positive_target_seconds": (
            positive_target_seconds
        ),

        "compared_seconds": compared,

        "comparison_coverage_ratio": round(
            coverage,
            4,
        ),

        "deviation_counts": dict(counts),

        "average_actual_power": None,

        "average_target_power": None,

        "average_signed_difference_watts": None,

        "mean_absolute_error_watts": None,

        "mean_absolute_relative_error_percent": None,

        "execution_ratio_percent": None,

        "within_target_percent": None,

        "zero_power_with_target_seconds": (
            counts["zero_power_with_target"]
        ),

        "actual_work_kj": None,

        "target_work_kj": None,

        "above_target_work_kj": None,

        "below_target_work_kj": None,
    }

    if not compared:
        return result

    status = (
        "ok"
        if coverage == 1.0
        else "partial"
    )

    return {
        **result,

        "status": status,

        "average_actual_power": round(
            mean(actual_values),
            2,
        ),

        "average_target_power": round(
            mean(target_values),
            2,
        ),

        "average_signed_difference_watts": round(
            mean(differences),
            2,
        ),

        "mean_absolute_error_watts": round(
            mean(
                abs(value)
                for value in differences
            ),
            2,
        ),

        "mean_absolute_relative_error_percent": round(
            mean(relative_errors) * 100,
            2,
        ),

        "execution_ratio_percent": round(
            sum(actual_values)
            / sum(target_values)
            * 100,
            2,
        ),

        "within_target_percent": round(
            counts["within_target"]
            / compared
            * 100,
            2,
        ),

        # Работа рассчитывается только
        # по совпадающим валидным отсчётам.

        "actual_work_kj": round(
            sum(actual_values) / 1000,
            3,
        ),

        "target_work_kj": round(
            sum(target_values) / 1000,
            3,
        ),

        "above_target_work_kj": round(
            above_target_work / 1000,
            3,
        ),

        "below_target_work_kj": round(
            below_target_work / 1000,
            3,
        ),
    }


def build_target_power_block(
    records,
    block_number,
):
    """
    Формирует описание непрерывного
    блока одинаковой целевой мощности.
    """
    target = get_valid_target_power(
        records[0]
    )

    if target is None:
        block_type = "missing_target"

    elif target == 0:
        block_type = "zero_target"

    else:
        block_type = "positive_target"

    execution = (
        calculate_target_execution_metrics(
            records
        )
    )

    return {
        "block_id": (
            f"target_block_{block_number}"
        ),

        "block_type": block_type,

        "start": records[0][
            "timestamp"
        ].isoformat(),

        "end": records[-1][
            "timestamp"
        ].isoformat(),

        "duration_seconds": len(records),

        "target_power": target,

        "execution": execution,
    }


def extract_target_power_blocks(
    records,
):
    """
    Выделяет непрерывные блоки
    одинаковой целевой мощности.

    Не объединяет блоки через
    отсутствующие временные записи.
    """
    indexed = prepare_effort_records(
        records
    )

    timestamps = sorted(indexed)

    blocks = []

    current = []

    previous_timestamp = None

    previous_target = None

    for timestamp in timestamps:
        record = {
            **indexed[timestamp],

            "timestamp": timestamp,
        }

        target = get_valid_target_power(
            record
        )

        if current:
            continuous = (
                timestamp
                - previous_timestamp
            ) == timedelta(seconds=1)

            same_target = (
                target == previous_target
            )

            if not (
                continuous
                and same_target
            ):
                blocks.append(
                    build_target_power_block(
                        records=current,

                        block_number=(
                            len(blocks) + 1
                        ),
                    )
                )

                current = []

        current.append(record)

        previous_timestamp = timestamp

        previous_target = target

    if current:
        blocks.append(
            build_target_power_block(
                records=current,

                block_number=len(blocks) + 1,
            )
        )

    return blocks


def build_target_deviation_event(
    records,
    event_type,
    event_number,
):
    """
    Описывает непрерывное отклонение
    от записанной целевой мощности.
    """
    metrics = (
        calculate_target_execution_metrics(
            records
        )
    )

    cadences = [
        get_valid_field(
            record,
            "cadence",
        )

        for record in records
    ]

    valid_cadences = [
        value
        for value in cadences
        if value is not None
    ]

    average_cadence = None

    if valid_cadences:
        average_cadence = round(
            mean(valid_cadences),
            2,
        )

    possible_cause = None

    if event_type == "zero_power_with_target":
        if len(valid_cadences) == len(records):
            if all(
                value == 0
                for value in valid_cadences
            ):
                possible_cause = (
                    "cessation_of_pedaling"
                )

            elif all(
                value >= 20
                for value in valid_cadences
            ):
                possible_cause = (
                    "possible_power_dropout"
                )

    return {
        "event_id": (
            f"target_deviation_{event_number}"
        ),

        "event_type": event_type,

        "start": records[0][
            "timestamp"
        ].isoformat(),

        "end": records[-1][
            "timestamp"
        ].isoformat(),

        "duration_seconds": len(records),

        "target_power": get_valid_target_power(
            records[0]
        ),

        "average_cadence": average_cadence,

        "possible_cause": possible_cause,

        "execution": metrics,

        "preserve_raw_records": True,
    }


def detect_target_deviation_events(
    records,
):
    """
    Обнаруживает непрерывные отклонения
    от положительной целевой мощности.

    Смена задания завершает событие.

    ЧСС не влияет на его границы.
    """
    indexed = prepare_effort_records(
        records
    )

    events = []

    current = []

    previous_timestamp = None

    previous_target = None

    previous_type = None

    for timestamp in sorted(indexed):
        record = {
            **indexed[timestamp],

            "timestamp": timestamp,
        }

        actual = get_valid_field(
            record,
            "power",
        )

        target = get_valid_target_power(
            record
        )

        event_type = classify_target_deviation(
            actual_power=actual,

            target_power=target,
        )

        is_event = event_type not in {
            "within_target",
            "target_unavailable",
        }

        if current:
            continuous = (
                timestamp
                - previous_timestamp
            ) == timedelta(seconds=1)

            same_target = (
                target == previous_target
            )

            same_type = (
                event_type == previous_type
            )

            if not (
                continuous
                and same_target
                and same_type
                and is_event
            ):
                events.append(
                    build_target_deviation_event(
                        records=current,

                        event_type=previous_type,

                        event_number=(
                            len(events) + 1
                        ),
                    )
                )

                current = []

        if is_event:
            current.append(record)

        previous_timestamp = timestamp

        previous_target = target

        previous_type = event_type

    if current:
        events.append(
            build_target_deviation_event(
                records=current,

                event_type=previous_type,

                event_number=len(events) + 1,
            )
        )

    return events


def analyze_workout_target_power(
    records,
    ignore_power=False,
):
    """
    Формирует полный анализ
    записанной целевой мощности.

    Не изменяет исходные FIT-записи.
    Не определяет режим ERG.
    Не оценивает физическую форму.
    """
    if not isinstance(ignore_power, bool):
        raise ValueError(
            "ignore_power должен быть bool"
        )

    availability = (
        assess_target_power_availability(
            records
        )
    )

    result = {
        "status": availability["status"],

        "target_availability": availability,

        "blocks": [],

        "deviation_events": [],

        "execution": None,

        "statistics": {
            "target_blocks_count": 0,

            "positive_target_blocks_count": 0,

            "deviation_events_count": 0,

            "deviation_event_type_counts": {},
        },

        "fitness_change": None,
    }

    if ignore_power:
        return {
            **result,

            "status": "power_ignored",

            "reason": (
                "Мощность исключена "
                "настройками активности"
            ),
        }

    if not availability[
        "usable_for_target_analysis"
    ]:
        return result

    indexed = prepare_effort_records(
        records
    )

    prepared = [
        {
            **indexed[timestamp],

            "timestamp": timestamp,
        }

        for timestamp in sorted(indexed)
    ]

    blocks = extract_target_power_blocks(
        prepared
    )

    events = detect_target_deviation_events(
        prepared
    )

    execution = (
        calculate_target_execution_metrics(
            prepared
        )
    )

    event_counts = Counter(
        event["event_type"]

        for event in events
    )

    return {
        **result,

        "status": execution["status"],

        "blocks": blocks,

        "deviation_events": events,

        "execution": execution,

        "statistics": {
            "target_blocks_count": len(
                blocks
            ),

            "positive_target_blocks_count": sum(
                block["block_type"]
                == "positive_target"

                for block in blocks
            ),

            "deviation_events_count": len(
                events
            ),

            "deviation_event_type_counts": dict(
                event_counts
            ),
        },

        "limitations": [
            (
                "Целевая мощность не заменяет "
                "фактически выполненную нагрузку"
            ),
            (
                "Кратковременные отклонения "
                "могут быть нормальной реакцией станка"
            ),
            (
                "Процент выполнения отражает "
                "отношение выполненной работы "
                "к целевой работе по доступным "
                "совпадающим измерениям"
            ),
            (
                "Превышение мощности может "
                "компенсировать недовыполнение "
                "в общей статистике"
            ),
            (
                "Нулевая цель не считается "
                "подтверждённым отдыхом"
            ),
            (
                "Причина отклонения и намерение "
                "спортсмена не установлены"
            ),
            (
                "Временные разрывы не заполняются"
            ),
        ],
    }