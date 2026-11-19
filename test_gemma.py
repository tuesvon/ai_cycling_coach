from src.assistant.llm import ask_gemma


question = (
    "Мой FTP составляет 304 Вт, вес 76.5 кг. "
    "Объясни, что означает показатель FTP на килограмм "
    "и как он используется в велосипедных тренировках."
)

answer = ask_gemma(question)

print("=== AI CYCLING COACH ===")
print(answer)
