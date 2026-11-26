from collections import Counter
from datetime import timedelta
from statistics import mean

from src.analytics.workout_comparison import (
    parse_activity_date,
)

from src.analytics.workout_effort_comparison import (
    prepare_effort_records,
    extract_record_window,
    get_valid_field,
    calculate_window_metrics,
)

from src.analytics.aerobic_segment_detection_v2 import (
    detect_aerobic_segments_v2,
)


MIN_HEART_RATE_COVERAGE = 0.90
MIN_DRIFT_SECONDS = 1200
MAX_HALF_POWER_DIFFERENCE_RATIO = 0.05

PREVIOUS_LOAD_SECONDS = 300

HIGH_INTENSITY_FTP_RATIO = 0.95


def calculate_efficiency_metrics(window):
    """
    Рассчитывает EF по синхронным измерениям
    мощности и ЧСС.

    Нулевые значения мощности сохраняются.
    Отсутствующие измерения не интерполируются.
    """
    pairs = []

    for record in window:
        power = get_valid_field(
            record, "power"
        )

        heart_rate = get_valid_field(
            record, "heart_rate"
        )

        if (
            power is not None
            and heart_rate is not None
        ):
            pairs.append(
                (power, heart_rate)
            )

    expected_seconds = len(window)

    coverage = (
        len(pairs) / expected_seconds
        if expected_seconds
        else 0
    )

    result = {
        "status": "insufficient_data",

        "method": "average_power_to_hr",

        "expected_seconds": expected_seconds,

        "paired_seconds": len(pairs),

        "paired_coverage_ratio": round(
            coverage, 4
        ),

        "average_paired_power": None,

        "average_paired_heart_rate": None,

        "efficiency_factor": None,
    }

    if (
        not pairs
        or coverage < MIN_HEART_RATE_COVERAGE
    ):
        return result

    average_power = mean(
        power
        for power, _ in pairs
    )

    average_heart_rate = mean(
        heart_rate
        for _, heart_rate in pairs
    )

    if (
        average_power <= 0
        or average_heart_rate <= 0
    ):
        return result

    return {
        **result,

        "status": (
            "ok"
            if coverage == 1
            else "partial"
        ),

        "average_paired_power": round(
            average_power, 2
        ),

        "average_paired_heart_rate": round(
            average_heart_rate, 2
        ),

        "efficiency_factor": round(
            average_power / average_heart_rate,
            6,
        ),
    }


def calculate_segment_drift(
    window,
    drift_candidate_by_power,
):
    """
    Рассчитывает изменение эффективности
    между равными половинами сегмента.

    Не объединяет отдельные сегменты.
    """
    result = {
        "status": "insufficient_data",

        "method": "average_power_to_hr",

        "drift_percent": None,

        "first_half": None,

        "second_half": None,

        "half_power_difference_percent": None,

        "heart_rate_difference_bpm": None,

        "excluded_middle_seconds": 0,

        "reasons": [],

        "fitness_change": None,
    }

    if not drift_candidate_by_power:
        result["reasons"].append(
            "not_drift_candidate_by_power"
        )

    if len(window) < MIN_DRIFT_SECONDS:
        result["reasons"].append(
            "insufficient_duration"
        )

    if result["reasons"]:
        return result

    if any(
        record is None
        or get_valid_field(record, "power")
        is None
        for record in window
    ):
        result["reasons"].append(
            "incomplete_time_or_power"
        )

        return result

    half_length = len(window) // 2

    first_window = window[:half_length]

    second_window = window[-half_length:]

    first = calculate_efficiency_metrics(
        first_window
    )

    second = calculate_efficiency_metrics(
        second_window
    )

    result["first_half"] = first

    result["second_half"] = second

    result["excluded_middle_seconds"] = (
        len(window) % 2
    )

    first_power = mean(
        get_valid_field(record, "power")
        for record in first_window
    )

    second_power = mean(
        get_valid_field(record, "power")
        for record in second_window
    )

    maximum_power = max(
        first_power,
        second_power,
    )

    if maximum_power <= 0:
        result["reasons"].append(
            "invalid_half_power"
        )

        return result

    power_difference = (
        abs(first_power - second_power)
        / maximum_power
    )

    result[
        "half_power_difference_percent"
    ] = round(
        power_difference * 100, 2
    )

    if (
        power_difference
        > MAX_HALF_POWER_DIFFERENCE_RATIO
    ):
        result["reasons"].append(
            "different_half_power"
        )

    if (
        first["efficiency_factor"] is None
        or second["efficiency_factor"] is None
    ):
        result["reasons"].append(
            "insufficient_paired_coverage"
        )

    if result["reasons"]:
        return result

    # Дополнительно проверяем, что отсутствующая
    # ЧСС не сместила выборку мощности.

    paired_first_power = first[
        "average_paired_power"
    ]

    paired_second_power = second[
        "average_paired_power"
    ]

    paired_difference = (
        abs(
            paired_first_power
            - paired_second_power
        )
        / max(
            paired_first_power,
            paired_second_power,
        )
    )

    if (
        paired_difference
        > MAX_HALF_POWER_DIFFERENCE_RATIO
    ):
        result["reasons"].append(
            "different_paired_half_power"
        )

        return result

    first_ef = first["efficiency_factor"]

    second_ef = second["efficiency_factor"]

    drift = (
        first_ef / second_ef - 1
    ) * 100

    heart_rate_difference = (
        second["average_paired_heart_rate"]
        - first["average_paired_heart_rate"]
    )

    return {
        **result,

        "status": (
            "ok"

            if (
                first["status"] == "ok"
                and second["status"] == "ok"
            )

            else "partial"
        ),

        "drift_percent": round(
            drift, 2
        ),

        "heart_rate_difference_bpm": round(
            heart_rate_difference, 2
        ),

        "paired_half_power_difference_percent": (
            round(
                paired_difference * 100, 2
            )
        ),
    }


def calculate_accumulated_load(
    indexed_records,
    segment_start,
    ftp,
):
    """
    Рассчитывает записанную работу
    от начала FIT до анализируемого сегмента.

    При неполных данных результат обозначается
    как частичный, а не полный объём работы.
    """
    timestamps = sorted(
        indexed_records
    )

    if not timestamps:
        return {
            "status": "insufficient_data",
        }

    workout_start = timestamps[0]

    elapsed_seconds = (
        segment_start - workout_start
    ).total_seconds()

    previous_records = [
        (timestamp, indexed_records[timestamp])

        for timestamp in timestamps

        if timestamp < segment_start
    ]

    valid_powers = []

    high_intensity_seconds = 0

    last_high_intensity_timestamp = None

    for timestamp, record in previous_records:
        power = get_valid_field(
            record, "power"
        )

        if power is None:
            continue

        valid_powers.append(power)

        if (
            power
            >= ftp * HIGH_INTENSITY_FTP_RATIO
        ):
            high_intensity_seconds += 1

            last_high_intensity_timestamp = (
                timestamp
            )

    complete_timing = (
        elapsed_seconds
        == len(previous_records)
    )

    if complete_timing:
        complete_timing = all(
            timestamp
            == workout_start
            + timedelta(seconds=index)

            for index, (timestamp, _) in enumerate(
                previous_records
            )
        )

    complete_power = (
        len(valid_powers)
        == len(previous_records)
    )

    complete = (
        complete_timing
        and complete_power
    )

    coverage = (
        min(
            1.0,
            len(valid_powers) / elapsed_seconds,
        )

        if elapsed_seconds > 0

        else 1.0
    )

    observed_work = (
        sum(valid_powers) / 1000
    )

    time_since_high_intensity = None

    if last_high_intensity_timestamp is not None:
        time_since_high_intensity = (
            segment_start
            - last_high_intensity_timestamp
        ).total_seconds()

    return {
        "status": (
            "ok"
            if complete
            else "partial"
        ),

        "reference": "first_fit_record",

        "workout_start": (
            workout_start.isoformat()
        ),

        "elapsed_seconds_before_segment": (
            elapsed_seconds
        ),

        "recorded_seconds_before_segment": len(
            previous_records
        ),

        "valid_power_seconds_before_segment": len(
            valid_powers
        ),

        "power_coverage_ratio": round(
            coverage, 4
        ),

        "complete_timing": complete_timing,

        "complete_power": complete_power,

        "observed_work_kj": round(
            observed_work, 3
        ),

        "total_work_kj": (
            round(observed_work, 3)
            if complete
            else None
        ),

        "observed_high_intensity_seconds": (
            high_intensity_seconds
        ),

        "seconds_since_last_observed_high_intensity": (
            time_since_high_intensity
        ),
    }


def analyze_aerobic_segment(
    segment,
    indexed_records,
    ftp,
):
    """
    Выполняет физиологический анализ
    одного принятого аэробного сегмента.
    """
    result = {
        "status": "insufficient_data",

        "segment_id": segment.get(
            "segment_id"
        ),

        "detection_method": segment.get(
            "detection_method"
        ),

        "target_power": segment.get(
            "target_power"
        ),

        "analysis_start": segment.get(
            "analysis_start"
        ),

        "analysis_end": segment.get(
            "analysis_end"
        ),

        "ftp": ftp,

        "metrics": None,

        "efficiency": None,

        "drift": None,

        "previous_load": None,

        "accumulated_load": None,

        "quality": None,

        "fitness_change": None,
    }

    if segment.get("status") != "accepted":
        return {
            **result,

            "reason": "segment_not_accepted",
        }

    start = parse_activity_date(
        segment["analysis_start"]
    )

    end = parse_activity_date(
        segment["analysis_end"]
    )

    duration = segment["metrics"][
        "duration_seconds"
    ]

    if (
        duration <= 0

        or (end - start).total_seconds() + 1
        != duration
    ):
        return {
            **result,

            "reason": "invalid_segment_duration",
        }

    window = extract_record_window(
        indexed_records=indexed_records,

        start=start,

        duration_seconds=duration,
    )

    metrics = calculate_window_metrics(
        window
    )

    result["metrics"] = metrics

    if not (
        metrics["complete_timing"]
        and metrics["complete_power"]
    ):
        return {
            **result,

            "reason": "incomplete_segment_data",
        }

    efficiency = (
        calculate_efficiency_metrics(
            window
        )
    )

    drift = calculate_segment_drift(
        window=window,

        drift_candidate_by_power=segment.get(
            "drift_candidate_by_power",
            False,
        ),
    )

    previous_window = extract_record_window(
        indexed_records=indexed_records,

        start=start - timedelta(
            seconds=PREVIOUS_LOAD_SECONDS
        ),

        duration_seconds=PREVIOUS_LOAD_SECONDS,
    )

    previous_load = calculate_window_metrics(
        previous_window
    )

    accumulated_load = (
        calculate_accumulated_load(
            indexed_records=indexed_records,

            segment_start=start,

            ftp=ftp,
        )
    )

    limitations = []

    if efficiency["status"] == "insufficient_data":
        limitations.append(
            "insufficient_heart_rate_data"
        )

    elif efficiency["status"] == "partial":
        limitations.append(
            "partial_heart_rate_coverage"
        )

    if accumulated_load["status"] != "ok":
        limitations.append(
            "incomplete_accumulated_load"
        )

    if not previous_load["complete_power"]:
        limitations.append(
            "incomplete_previous_load"
        )

    if metrics["cadence_coverage_ratio"] < 0.90:
        limitations.append(
            "insufficient_cadence_coverage"
        )

    if (
        segment.get("drift_candidate_by_power")
        and drift["status"] != "ok"
    ):
        limitations.append(
            "drift_unavailable_or_partial"
        )

    return {
        **result,

        "status": (
            "partial"
            if limitations
            else "ok"
        ),

        "duration_seconds": duration,

        "bridge_seconds": segment.get(
            "bridge_seconds", 0
        ),

        "transient_seconds": segment.get(
            "transient_seconds", 0
        ),

        "metrics": metrics,

        "efficiency": efficiency,

        "drift": drift,

        "previous_load": previous_load,

        "accumulated_load": accumulated_load,

        "quality": {
            "heart_rate_analysis_available": (
                efficiency["efficiency_factor"]
                is not None
            ),

            "drift_available": (
                drift["drift_percent"]
                is not None
            ),

            "complete_accumulated_load": (
                accumulated_load["status"]
                == "ok"
            ),

            "limitations": limitations,
        },
    }


def analyze_aerobic_workout(
    records,
    ftp,
    riding_mode="unknown",
    ignore_power=False,
    ignore_heart_rate=False,
):
    """
    Обнаруживает аэробные сегменты
    и рассчитывает физиологические метрики.

    Не объединяет отдельные аэробные блоки
    в один искусственный сегмент.
    """
    if not isinstance(ignore_power, bool):
        raise ValueError(
            "ignore_power должен быть bool"
        )

    if not isinstance(ignore_heart_rate, bool):
        raise ValueError(
            "ignore_heart_rate должен быть bool"
        )

    detection = detect_aerobic_segments_v2(
        records=records,

        ftp=ftp,

        riding_mode=riding_mode,

        ignore_power=ignore_power,

        ignore_heart_rate=ignore_heart_rate,
    )

    result = {
        "status": detection["status"],

        "ftp": ftp,

        "detection": detection,

        "segments": [],

        "summary": {
            "detected_segments_count": len(
                detection["segments"]
            ),

            "analyzed_segments_count": 0,

            "heart_rate_segments_count": 0,

            "drift_segments_count": 0,

            "total_analyzed_seconds": 0,

            "total_analyzed_minutes": 0,

            "analysis_status_counts": {},
        },

        "ignore_power": ignore_power,

        "ignore_heart_rate": ignore_heart_rate,

        "fitness_change": None,
    }

    if detection["status"] != "ok":
        return result

    prepared_records = []

    for record in records:
        if not isinstance(record, dict):
            continue

        copied = dict(record)

        if ignore_heart_rate:
            copied.pop(
                "heart_rate", None
            )

        prepared_records.append(copied)

    indexed = prepare_effort_records(
        prepared_records
    )

    analyzed = [
        analyze_aerobic_segment(
            segment=segment,

            indexed_records=indexed,

            ftp=ftp,
        )

        for segment in detection["segments"]
    ]

    status_counts = Counter(
        segment["status"]
        for segment in analyzed
    )

    valid_segments = [
        segment

        for segment in analyzed

        if segment["status"] in {
            "ok", "partial"
        }
    ]

    heart_rate_segments = [
        segment

        for segment in valid_segments

        if segment["quality"][
            "heart_rate_analysis_available"
        ]
    ]

    drift_segments = [
        segment

        for segment in valid_segments

        if segment["quality"][
            "drift_available"
        ]
    ]

    total_seconds = sum(
        segment["duration_seconds"]
        for segment in valid_segments
    )

    if not valid_segments:
        status = "insufficient_data"

    elif any(
        segment["status"] != "ok"
        for segment in analyzed
    ):
        status = "partial"

    else:
        status = "ok"

    return {
        **result,

        "status": status,

        "segments": analyzed,

        "summary": {
            "detected_segments_count": len(
                detection["segments"]
            ),

            "analyzed_segments_count": len(
                valid_segments
            ),

            "heart_rate_segments_count": len(
                heart_rate_segments
            ),

            "drift_segments_count": len(
                drift_segments
            ),

            "total_analyzed_seconds": (
                total_seconds
            ),

            "total_analyzed_minutes": round(
                total_seconds / 60, 2
            ),

            "analysis_status_counts": dict(
                status_counts
            ),
        },

        "limitations": [
            (
                "EF рассчитывается по средней "
                "фактической мощности и ЧСС"
            ),
            (
                "Для EF используются только "
                "синхронные измерения"
            ),
            (
                "Отдельные сегменты не объединяются "
                "для расчёта дрейфа"
            ),
            (
                "Накопленная работа при пропусках "
                "отражает только записанные данные"
            ),
            (
                "Отсчёт накопленной нагрузки "
                "начинается с первой записи FIT"
            ),
            (
                "Высокая интенсивность определяется "
                "по мощности отдельных секунд, "
                "а не по структуре усилий"
            ),
            (
                "Температура, гидратация, питание "
                "и другие условия требуют "
                "дополнительной оценки"
            ),
            (
                "Изменение EF или дрейфа "
                "не доказывает изменение "
                "физической формы"
            ),
        ],
    }