from collections import Counter
from datetime import timedelta
from statistics import mean

from src.analytics.workout_classification import (
    is_valid_number,
)

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    extract_record_window,
)

from src.analytics.workout_target_power import (
    assess_target_power_availability,
    extract_target_power_blocks,
    calculate_target_execution_metrics,
)


MIN_RAMP_STEPS = 3

MAX_RAMP_STEP_SECONDS = 60

MAX_RAMP_STEP_WATTS = 5

MAX_RAMP_STEP_RATIO = 0.02

MIN_RAMP_TOTAL_CHANGE_WATTS = 5


def are_blocks_continuous(first, second):
    """
    Проверяет непрерывность двух
    последовательных целевых блоков.
    """
    first_end = parse_activity_date(
        first["end"]
    )

    second_start = parse_activity_date(
        second["start"]
    )

    return (
        second_start - first_end
        == timedelta(seconds=1)
    )


def is_positive_target_block(block):
    """
    Проверяет наличие положительной
    целевой мощности.
    """
    target = block.get("target_power")

    return (
        is_valid_number(target)
        and target > 0
    )


def get_target_step_direction(first, second):
    """
    Определяет направление небольшого
    изменения целевой мощности.

    Возвращает:
        1  - увеличение;
        -1 - снижение;
        0  - переход не подходит для Ramp.
    """
    if not (
        is_positive_target_block(first)
        and is_positive_target_block(second)
    ):
        return 0

    if not are_blocks_continuous(
        first,
        second,
    ):
        return 0

    if (
        first["duration_seconds"]
        > MAX_RAMP_STEP_SECONDS

        or second["duration_seconds"]
        > MAX_RAMP_STEP_SECONDS
    ):
        return 0

    first_power = first["target_power"]

    second_power = second["target_power"]

    difference = (
        second_power - first_power
    )

    maximum_step = max(
        MAX_RAMP_STEP_WATTS,

        first_power * MAX_RAMP_STEP_RATIO,
    )

    if abs(difference) > maximum_step:
        return 0

    if difference > 0:
        return 1

    if difference < 0:
        return -1

    return 0


def find_ramp_end_index(
    blocks,
    start_index,
):
    """
    Ищет конец последовательности
    однонаправленных небольших
    изменений целевой мощности.

    Если Ramp не обнаружен,
    возвращает start_index.
    """
    if start_index + 1 >= len(blocks):
        return start_index

    direction = get_target_step_direction(
        blocks[start_index],

        blocks[start_index + 1],
    )

    if direction == 0:
        return start_index

    end_index = start_index + 1

    while end_index + 1 < len(blocks):
        next_direction = (
            get_target_step_direction(
                blocks[end_index],

                blocks[end_index + 1],
            )
        )

        if next_direction != direction:
            break

        end_index += 1

    steps_count = (
        end_index - start_index + 1
    )

    if steps_count < MIN_RAMP_STEPS:
        return start_index

    first_power = blocks[
        start_index
    ]["target_power"]

    last_power = blocks[
        end_index
    ]["target_power"]

    total_change = abs(
        last_power - first_power
    )

    if (
        total_change
        < MIN_RAMP_TOTAL_CHANGE_WATTS
    ):
        return start_index

    return end_index


def classify_target_intensity(
    target_power,
    ftp,
):
    """
    Классифицирует целевую
    интенсивность относительно FTP.

    Категории описывают мощность,
    а не подтверждённое
    физиологическое состояние.
    """
    if (
        not is_valid_number(ftp)
        or ftp <= 0
        or not is_valid_number(target_power)
        or target_power <= 0
    ):
        return "unknown"

    ratio = target_power / ftp

    if ratio <= 0.55:
        return "recovery"

    if ratio <= 0.75:
        return "endurance"

    if ratio < 0.88:
        return "tempo"

    if ratio < 0.95:
        return "sweet_spot"

    if ratio <= 1.05:
        return "threshold"

    if ratio <= 1.20:
        return "vo2max_power"

    if ratio <= 1.50:
        return "anaerobic_power"

    return "very_high_intensity"


def get_structure_block_type(blocks):
    """
    Определяет тип объединённого
    тренировочного блока.
    """
    if len(blocks) > 1:
        first = blocks[0]["target_power"]

        last = blocks[-1]["target_power"]

        if last > first:
            return "ramp_up"

        return "ramp_down"

    target = blocks[0].get(
        "target_power"
    )

    if target is None:
        return "missing_target"

    if target == 0:
        return "zero_target"

    return "steady"


def build_structure_block(
    source_blocks,
    indexed_records,
    block_number,
    ftp=None,
):
    """
    Формирует логический блок
    тренировочного задания.

    Метрики выполнения рассчитываются
    заново по исходным FIT-записям,
    а не усреднением готовых метрик.
    """
    if not source_blocks:
        raise ValueError(
            "Не переданы целевые блоки"
        )

    for first, second in zip(
        source_blocks,
        source_blocks[1:],
    ):
        if not are_blocks_continuous(
            first,
            second,
        ):
            raise ValueError(
                "Нельзя объединять блоки "
                "через временной разрыв"
            )

    start = parse_activity_date(
        source_blocks[0]["start"]
    )

    end = parse_activity_date(
        source_blocks[-1]["end"]
    )

    duration = sum(
        block["duration_seconds"]

        for block in source_blocks
    )

    expected_duration = int(
        (end - start).total_seconds()
    ) + 1

    if duration != expected_duration:
        raise ValueError(
            "Некорректная длительность блока"
        )

    block_type = get_structure_block_type(
        source_blocks
    )

    records = extract_record_window(
        indexed_records=indexed_records,

        start=start,

        duration_seconds=duration,
    )

    if any(
        record is None

        for record in records
    ):
        raise ValueError(
            "Внутри блока отсутствуют "
            "временные записи"
        )

    execution = (
        calculate_target_execution_metrics(
            records
        )
    )

    positive_targets = []

    intensity_seconds = Counter()

    for block in source_blocks:
        target = block.get(
            "target_power"
        )

        block_duration = block[
            "duration_seconds"
        ]

        intensity = classify_target_intensity(
            target_power=target,

            ftp=ftp,
        )

        intensity_seconds[
            intensity
        ] += block_duration

        if (
            is_valid_number(target)
            and target > 0
        ):
            positive_targets.extend(
                [target] * block_duration
            )

    average_target = (
        mean(positive_targets)
        if positive_targets
        else None
    )

    relative_target = None

    if (
        average_target is not None
        and is_valid_number(ftp)
        and ftp > 0
    ):
        relative_target = round(
            average_target / ftp * 100,
            2,
        )

    return {
        "block_id": (
            f"structure_block_{block_number}"
        ),

        "block_type": block_type,

        "start": start.isoformat(),

        "end": end.isoformat(),

        "duration_seconds": duration,

        "source_blocks_count": len(
            source_blocks
        ),

        "source_block_ids": [
            block["block_id"]

            for block in source_blocks
        ],

        "start_target_power": (
            source_blocks[0]["target_power"]
        ),

        "end_target_power": (
            source_blocks[-1]["target_power"]
        ),

        "average_target_power": (
            round(average_target, 2)

            if average_target is not None

            else None
        ),

        "minimum_target_power": (
            min(positive_targets)

            if positive_targets

            else None
        ),

        "maximum_target_power": (
            max(positive_targets)

            if positive_targets

            else None
        ),

        "average_target_ftp_percent": (
            relative_target
        ),

        "intensity_category": (
            classify_target_intensity(
                target_power=average_target,

                ftp=ftp,
            )
        ),

        "intensity_distribution_seconds": (
            dict(intensity_seconds)
        ),

        "execution": execution,
    }


def group_target_power_blocks(
    blocks,
    records,
    ftp=None,
):
    """
    Преобразует исходные целевые блоки
    в логическую тренировочную структуру.

    Каждый исходный блок включается
    ровно в один логический блок.
    """
    indexed_records = (
        prepare_effort_records(
            records
        )
    )

    grouped = []

    index = 0

    while index < len(blocks):
        ramp_end = find_ramp_end_index(
            blocks=blocks,

            start_index=index,
        )

        selected_blocks = blocks[
            index:ramp_end + 1
        ]

        structure_block = (
            build_structure_block(
                source_blocks=selected_blocks,

                indexed_records=indexed_records,

                block_number=len(grouped) + 1,

                ftp=ftp,
            )
        )

        grouped.append(
            structure_block
        )

        index = ramp_end + 1

    return grouped


def summarize_target_structure(blocks):
    """
    Формирует статистику логических
    тренировочных блоков.
    """
    block_type_counts = Counter()

    intensity_distribution = Counter()

    total_duration = 0

    source_blocks_count = 0

    total_work_kj = 0.0

    total_target_work_kj = 0.0

    compared_seconds = 0

    for block in blocks:
        block_type = block[
            "block_type"
        ]

        block_type_counts[
            block_type
        ] += 1

        intensity_distribution.update(
            block[
                "intensity_distribution_seconds"
            ]
        )

        total_duration += block[
            "duration_seconds"
        ]

        source_blocks_count += block[
            "source_blocks_count"
        ]

        execution = block[
            "execution"
        ]

        actual_work = execution.get(
            "actual_work_kj"
        )

        target_work = execution.get(
            "target_work_kj"
        )

        if actual_work is not None:
            total_work_kj += actual_work

        if target_work is not None:
            total_target_work_kj += target_work

        compared_seconds += execution.get(
            "compared_seconds", 0
        )

    reduction_percent = None

    if source_blocks_count:
        reduction_percent = round(
            (
                1
                - len(blocks)
                / source_blocks_count
            ) * 100,
            2,
        )

    return {
        "source_blocks_count": (
            source_blocks_count
        ),

        "structure_blocks_count": len(
            blocks
        ),

        "blocks_reduction_percent": (
            reduction_percent
        ),

        "block_type_counts": dict(
            block_type_counts
        ),

        "intensity_distribution_seconds": (
            dict(intensity_distribution)
        ),

        "recorded_duration_seconds": (
            total_duration
        ),

        "compared_seconds": (
            compared_seconds
        ),

        "actual_work_kj_in_compared_records": (
            round(total_work_kj, 3)

            if compared_seconds

            else None
        ),

        "target_work_kj_in_compared_records": (
            round(total_target_work_kj, 3)

            if compared_seconds

            else None
        ),
    }


def analyze_workout_target_structure(
    records,
    ftp=None,
    ignore_power=False,
):
    """
    Формирует логическую структуру
    записанного тренировочного задания.

    Не подменяет фактическую
    структуру нагрузки целевой.

    Не использует ЧСС для
    определения границ блоков.
    """
    if not isinstance(ignore_power, bool):
        raise ValueError(
            "ignore_power должен быть bool"
        )

    if ftp is not None:
        if (
            not is_valid_number(ftp)
            or ftp <= 0
        ):
            raise ValueError(
                "Некорректный FTP"
            )

    result = {
        "status": "insufficient_data",

        "ftp": ftp,

        "structure_source": (
            "fit.record.target_power"
        ),

        "target_availability": None,

        "source_blocks": [],

        "structure_blocks": [],

        "statistics": (
            summarize_target_structure([])
        ),

        "execution": None,

        "fitness_change": None,
    }

    if ignore_power:
        return {
            **result,

            "status": "power_ignored",
        }

    availability = (
        assess_target_power_availability(
            records
        )
    )

    result["target_availability"] = (
        availability
    )

    if not availability[
        "usable_for_target_analysis"
    ]:
        return {
            **result,

            "status": availability["status"],
        }

    source_blocks = (
        extract_target_power_blocks(
            records
        )
    )

    structure_blocks = (
        group_target_power_blocks(
            blocks=source_blocks,

            records=records,

            ftp=ftp,
        )
    )

    indexed = prepare_effort_records(
        records
    )

    prepared = [
        indexed[timestamp]

        for timestamp in sorted(indexed)
    ]

    execution = (
        calculate_target_execution_metrics(
            prepared
        )
    )

    statistics = (
        summarize_target_structure(
            structure_blocks
        )
    )

    return {
        **result,

        "status": (
            "ok"
            if structure_blocks
            else "insufficient_data"
        ),

        "source_blocks": source_blocks,

        "structure_blocks": (
            structure_blocks
        ),

        "statistics": statistics,

        "execution": execution,

        "settings": {
            "minimum_ramp_steps": (
                MIN_RAMP_STEPS
            ),

            "maximum_ramp_step_seconds": (
                MAX_RAMP_STEP_SECONDS
            ),

            "maximum_ramp_step_watts": (
                MAX_RAMP_STEP_WATTS
            ),

            "maximum_ramp_step_ratio": (
                MAX_RAMP_STEP_RATIO
            ),

            "minimum_ramp_total_change_watts": (
                MIN_RAMP_TOTAL_CHANGE_WATTS
            ),
        },

        "limitations": [
            (
                "Ramp определяется эвристически "
                "по последовательным изменениям "
                "целевой мощности"
            ),
            (
                "Ramp не обязательно является "
                "разминкой или заминкой"
            ),
            (
                "Целевая структура не подтверждает "
                "фактическое выполнение задания"
            ),
            (
                "Нулевая цель не считается "
                "подтверждённым отдыхом"
            ),
            (
                "Категории интенсивности "
                "определяются относительно "
                "переданного FTP"
            ),
            (
                "Временные разрывы "
                "не объединяются"
            ),
            (
                "Режим ERG автоматически "
                "не подтверждается"
            ),
            (
                "Сложные повторяющиеся группы "
                "интервалов пока не выделяются"
            ),
            (
                "Общий статус отражает "
                "доступность структуры, "
                "а не качество выполнения"
            ),
        ],
    }