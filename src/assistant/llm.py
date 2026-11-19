from openai import OpenAI


client = OpenAI(
    base_url="http://localhost:1235/v1",
    api_key="not-needed"
)

MODEL_NAME = "google/gemma-4-e4b"


def ask_gemma(message):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — профессиональный AI Cycling Coach. "
                    "Помогаешь анализировать велосипедные тренировки "
                    "и давать рекомендации спортсменам. "
                    "Отвечай на русском языке."
                )
            },
            {
                "role": "user",
                "content": message
            }
        ],
        temperature=0.7
    )

    return response.choices[0].message.content
