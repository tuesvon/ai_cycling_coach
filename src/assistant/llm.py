from openai import OpenAI


client = OpenAI(
    base_url="http://localhost:1235/v1",
    api_key="not-needed"
)

MODEL_NAME = "google/gemma-4-e4b"

DEFAULT_SYSTEM_PROMPT = (
    "Ты — профессиональный AI Cycling Coach. "
    "Помогаешь анализировать велосипедные тренировки "
    "и давать рекомендации спортсменам. "
    "Отвечай на русском языке. "
    "Опирайся на предоставленные данные. "
    "Не выдумывай показатели, события и результаты тренировок. "
    "Если данных недостаточно, прямо сообщи об этом. "
    "Отделяй факты от предположений и рекомендаций. "
    "Не ставь медицинские диагнозы."
)


def ask_gemma(message, system_prompt=None):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt or DEFAULT_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": message
            }
        ],
        temperature=0.7
    )

    return response.choices[0].message.content