def classify(value: int | str) -> str:
    captured: int | str = "old"
    match value:
        case captured if isinstance(captured, int):
            return "int"
        case _:
            return "other"
print(classify(1), classify("s"))
