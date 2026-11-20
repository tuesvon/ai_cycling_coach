
import json

from src.analytics.athlete_analysis import get_registered_athlete_analysis
from src.assistant.llm import ask_gemma


COACH_SYSTEM_PROMPT = """
Ты — персональный AI Cycling Coach.

Твоя задача — анализировать тренировочные данные спортсмена
и помогать ему принимать решения относительно тренировок.

СТРОГИЕ ПРАВИЛА РАБОТЫ С ДАННЫМИ:

1. Все числовые показатели уже рассчитаны Python.
   Не пересчитывай их самостоятельно.

2. Не изменяй значения, периоды, единицы измерения
   и названия метрик.

3. Не называй сумму средним значением и наоборот.

4. Не смешивай Garmin Load и TSS.
   Это разные метрики, их нельзя складывать или сравнивать
   как одинаковые величины.

5. Не смешивай велосипедные тренировки с ходьбой,
   силовыми и другими активностями.

6. Всегда указывай период, к которому относится показатель.

7. Если данных недостаточно или покрытие неполное,
   прямо сообщи об этом. Не делай выводов по отсутствующим данным.

8. Не придумывай показатели, тренировки, события
   и причины изменения нагрузки.

9. При анализе HRV и пульса покоя сравнивай показатели
   только с переданной личной базой спортсмена.
   Не делай медицинских выводов.

10. Используй переданные границы зон мощности в ваттах.
    Не пересчитывай FTP и зоны самостоятельно.
    Не путай процент FTP с абсолютной мощностью.

11. Не назначай конкретную тренировку как обязательную,
    если для этого недостаточно данных о состоянии спортсмена,
    его субъективной усталости и расписании.

12. Разделяй объективные факты, интерпретацию
    и рекомендации.

13. Если есть противоречия между показателями,
    укажи на них, а не выбирай удобный показатель.

14. Отвечай на русском языке.

15. Не делай выводов о физической форме, состоянии
    нервной системы, переутомлении или перетренированности
    на основании одного или нескольких отдельных показателей.

16. Повышенный HRV относительно личной базы сам по себе
    не доказывает хорошее восстановление.
    Пониженный RHR сам по себе не доказывает хорошую
    физическую форму или адаптацию.

17. Не называй недосып хроническим, если нет данных,
    подтверждающих его регулярное повторение.

18. Не используй медицинские или категоричные оценки
    вроде "критическое состояние", "красный флаг",
    "организм истощён", если аналитическая система
    явно не передала такую оценку.

19. Рост Garmin Load или ATL/CTL сам по себе
    не доказывает переутомление.
    Учитывай качество и полноту данных.

20. Различай:
    - объективно измеренные показатели;
    - оценки аналитической системы;
    - собственные предположения.
    Не представляй предположения как факты.

21. Если readiness имеет значение mixed,
    объясни, какие именно показатели повлияли на оценку.
    Не превращай mixed автоматически в рекомендацию
    полностью отказаться от тренировок.

22. Если спортсмен спрашивает, как тренироваться сегодня,
    сначала оцени доступные данные о нагрузке и восстановлении.
    Если информации недостаточно для назначения интенсивности,
    предложи осторожный вариант тренировки и укажи,
    каких данных не хватает для более точной рекомендации.

23. Не называй нагрузку устойчиво растущей или снижающейся,
    если анализируется только сравнение двух периодов.
    Указывай конкретно: "значение за последние 7 дней выше
    недельного среднего предыдущих 23 дней на X%".

24. Средние значения за 7 или 30 дней являются историческими
    ориентирами, а не целевыми значениями.
    Не предписывай спортсмену достигать или превышать
    средний Sleep Score, HRV или другие показатели.

25. Readiness — аналитическая оценка состояния, а не запрет
    или разрешение на тренировку.
    Не утверждай, что система запрещает определённые зоны
    или интенсивность.

26. Не назначай продолжительность тренировки в минутах,
    если она не рассчитана Python или не следует из плана
    спортсмена. Не придумывай ограничения по времени.

27. Если предлагаешь тренировку, отделяй фактические данные
    от примерного тренировочного предложения.
    Не представляй рекомендацию модели как обязательное
    предписание тренера.

28. Не путай средние значения за 7 дней и за 30 дней.
    Всегда указывай точный период каждого показателя.
    
"""


def build_power_zones_watts(profile):
    """
    Рассчитывает границы велосипедных зон мощности в ваттах.
    Использует верхние границы зон Intervals.icu.
    """
    ftp = profile.get("ftp")
    percentages = profile.get("power_zones") or []
    names = profile.get("power_zone_names") or []

    if ftp is None or not percentages or not names:
        return []

    zones = []
    lower = 1

    for index, percentage in enumerate(percentages):
        if index >= len(names):
            break

        if percentage >= 999:
            upper = None
        else:
            upper = int(ftp * percentage / 100)

        zones.append({
            "zone": index + 1,
            "name": names[index],
            "min_watts": lower,
            "max_watts": upper
        })

        if upper is not None:
            lower = upper + 1

    return zones


def build_coach_context(analysis):
    """
    Формирует структурированный аналитический контекст.
    Включает только необходимые для тренера показатели.
    """

    profile = analysis.get("profile") or {}
    training_load = analysis.get("training_load") or {}
    trends = analysis.get("training_load_trends") or {}
    training_7 = training_load.get("7_days") or {}
    training_30 = training_load.get("30_days") or {}

    cycling_7 = (training_7.get("by_type") or {}).get("cycling") or {}
    cycling_30 = (training_30.get("by_type") or {}).get("cycling") or {}

    trend_periods = trends.get("periods") or {}
    trend_comparison = trends.get("comparison") or {}

    context = {
        "profile": {
            "name": profile.get("name"),
            "weight_kg": profile.get("weight"),
            "ftp_watts": profile.get("ftp"),
            "ftp_per_kg": profile.get("ftp_per_kg"),
            "lthr_bpm": profile.get("lthr"),
            "max_heart_rate_bpm": profile.get("max_heart_rate")
        },

        "power_zones_watts": build_power_zones_watts(profile),

        "readiness": analysis.get("readiness"),

        "cycling_training_load": {
            "last_7_days": {
                "activities_count": cycling_7.get("activities_count"),
                "duration_hours": cycling_7.get("total_duration_hours"),
                "tss_total": cycling_7.get("total_tss"),
                "tss_records_count": cycling_7.get("tss_activities_count"),
                "garmin_load_total": cycling_7.get("total_garmin_load"),
                "garmin_load_records_count": cycling_7.get("garmin_load_activities_count")
            },

            "last_30_days": {
                "activities_count": cycling_30.get("activities_count"),
                "duration_hours": cycling_30.get("total_duration_hours"),
                "tss_total": cycling_30.get("total_tss"),
                "tss_records_count": cycling_30.get("tss_activities_count"),
                "garmin_load_total": cycling_30.get("total_garmin_load"),
                "garmin_load_records_count": cycling_30.get("garmin_load_activities_count")
            },

            "last_7_days_vs_previous_23_days": {
                "periods": trend_periods,
                "comparison": trend_comparison
            }
        },

        "recovery": analysis.get("recovery"),

        "training_history": analysis.get("training_history"),

        "training_trends": analysis.get("training_trends"),

        "training_consistency": analysis.get("training_consistency")
    }

    return context


def build_coach_prompt(analysis, question):
    context = build_coach_context(analysis)

    context_json = json.dumps(
        context,
        ensure_ascii=False,
        indent=2,
        default=str
    )

    return (
        "Проанализируй данные спортсмена и ответь на его вопрос.\n\n"
        "ВАЖНО: используй числовые показатели строго в том виде, "
        "в котором они переданы. Не пересчитывай их.\n\n"
        f"ДАННЫЕ СПОРТСМЕНА:\n{context_json}\n\n"
        f"ВОПРОС СПОРТСМЕНА:\n{question}"
    )


def ask_coach(athlete_id, question):
    """
    Получает актуальный анализ спортсмена
    и передаёт его Gemma.
    """
    analysis = get_registered_athlete_analysis(athlete_id)
    prompt = build_coach_prompt(analysis, question)

    return ask_gemma(
        prompt,
        system_prompt=COACH_SYSTEM_PROMPT
    )
