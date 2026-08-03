ANSWER_WORDS: dict[int, tuple[str, str]] = {
    0: ("ноль", "zero"),
    1: ("один", "one"),
    2: ("два", "two"),
    3: ("три", "three"),
    4: ("четыре", "four"),
    5: ("пять", "five"),
    6: ("шесть", "six"),
    7: ("семь", "seven"),
    8: ("восемь", "eight"),
    9: ("девять", "nine"),
    10: ("десять", "ten"),
    11: ("одиннадцать", "eleven"),
    12: ("двенадцать", "twelve"),
    13: ("тринадцать", "thirteen"),
    14: ("четырнадцать", "fourteen"),
    15: ("пятнадцать", "fifteen"),
    16: ("шестнадцать", "sixteen"),
    17: ("семнадцать", "seventeen"),
    18: ("восемнадцать", "eighteen"),
    19: ("девятнадцать", "nineteen"),
    20: ("двадцать", "twenty"),
}


def normalize_answer(value: str) -> str:
    normalized = value.lower().replace("ё", "е")
    normalized = normalized.replace("-", " ").replace("–", " ").replace("—", " ")
    return " ".join(normalized.split())


def is_correct_answer(value: str, expected: int) -> bool:
    # Digits are explicitly not accepted, including Unicode digit characters.
    if any(character.isdigit() for character in value):
        return False
    if expected not in ANSWER_WORDS:
        return False
    return normalize_answer(value) in {
        normalize_answer(word) for word in ANSWER_WORDS[expected]
    }
