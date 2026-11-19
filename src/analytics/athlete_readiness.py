
def calculate_change_percent(current, baseline):
    if current is None or baseline is None or baseline == 0:
        return None

    return round((current - baseline) / baseline * 100, 1)


def evaluate_sleep(recovery):
    latest = recovery.get("latest_sleep")

    if not latest:
        return {
            "status": "unknown",
            "message": "Нет данных о сне"
        }

    sleep_hours = latest.get("sleep_hours")
    sleep_score = latest.get("sleep_score")
    baseline_score = recovery.get("average_sleep_score")

    issues = []

    if sleep_hours is not None and sleep_hours < 6:
        issues.append("Продолжительность сна менее 6 часов")

    if (
        sleep_score is not None
        and baseline_score is not None
        and sleep_score < baseline_score * 0.85
    ):
        issues.append("Sleep Score заметно ниже личного среднего")

    return {
        "status": "attention" if issues else "normal",
        "sleep_hours": sleep_hours,
        "sleep_score": sleep_score,
        "issues": issues
    }


def evaluate_hrv(recovery_7, recovery_30):
    latest = recovery_7.get("latest_recovery")

    if not latest:
        return {"status": "unknown"}

    current = latest.get("hrv")
    baseline = recovery_30.get("average_hrv")

    change = calculate_change_percent(current, baseline)

    if change is None:
        status = "unknown"
    elif change <= -10:
        status = "attention"
    else:
        status = "normal"

    return {
        "status": status,
        "current": current,
        "baseline": baseline,
        "change_percent": change
    }


def evaluate_resting_hr(recovery_7, recovery_30):
    latest = recovery_7.get("latest_recovery")

    if not latest:
        return {"status": "unknown"}

    current = latest.get("resting_hr")
    baseline = recovery_30.get("average_resting_hr")

    change = None

    if current is not None and baseline is not None:
        change = round(current - baseline, 1)

    if change is None:
        status = "unknown"
    elif change >= 5:
        status = "attention"
    else:
        status = "normal"

    return {
        "status": status,
        "current": current,
        "baseline": baseline,
        "difference": change
    }


def evaluate_training_load(recovery_7):
    latest = recovery_7.get("latest_recovery")

    if not latest:
        return {"status": "unknown"}

    atl = latest.get("atl")
    ctl = latest.get("ctl")
    ramp_rate = latest.get("ramp_rate")

    ratio = None

    if atl is not None and ctl is not None and ctl > 0:
        ratio = round(atl / ctl, 2)

    return {
        "status": "informational",
        "atl": atl,
        "ctl": ctl,
        "atl_ctl_ratio": ratio,
        "ramp_rate": ramp_rate
    }


def evaluate_readiness(status):
    recovery_7 = status["recovery"]["7_days"]
    recovery_30 = status["recovery"]["30_days"]

    sleep = evaluate_sleep(recovery_7)
    hrv = evaluate_hrv(recovery_7, recovery_30)
    resting_hr = evaluate_resting_hr(recovery_7, recovery_30)
    training = evaluate_training_load(recovery_7)

    attention_count = sum(
        item["status"] == "attention"
        for item in [sleep, hrv, resting_hr]
    )

    if attention_count == 0:
        overall = "good"
    elif attention_count == 1:
        overall = "mixed"
    else:
        overall = "low"

    return {
        "overall": overall,
        "signals": {
            "sleep": sleep,
            "hrv": hrv,
            "resting_hr": resting_hr,
            "training_load": training
        }
    }