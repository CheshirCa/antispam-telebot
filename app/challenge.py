from dataclasses import dataclass
import random

from .words import ANSWER_WORDS


@dataclass(frozen=True, slots=True)
class GeneratedChallenge:
    left: int
    operator: str
    right: int
    answer: int

    def text(self, timeout_minutes: int = 5) -> str:
        return (
            "Здравствуйте! / Hello!\n\n"
            "Для защиты группы от спама решите пример. / "
            "To protect the group from spam, solve the problem.\n\n"
            f"{self.left} {self.operator} {self.right} = ?\n\n"
            "Ответ напишите СЛОВОМ на русском или английском языке. / "
            "Write the answer as a WORD in Russian or English.\n\n"
            "Например / Example: пятнадцать или / or fifteen\n\n"
            f"На выполнение даётся {timeout_minutes} минут. / You have {timeout_minutes} minutes."
        )


def generate_challenge() -> GeneratedChallenge:
    operation = random.choice(("+", "-", "×"))
    if operation == "+":
        left = random.randint(0, 20)
        right = random.randint(0, 20 - left)
        answer = left + right
    elif operation == "-":
        left = random.randint(0, 20)
        right = random.randint(0, left)
        answer = left - right
    else:
        factors = [(left, right) for left in range(21) for right in range(21)
                   if left * right <= 20]
        left, right = random.choice(factors)
        answer = left * right
    assert 0 <= answer <= 20 and answer in ANSWER_WORDS
    return GeneratedChallenge(left, operation, right, answer)
