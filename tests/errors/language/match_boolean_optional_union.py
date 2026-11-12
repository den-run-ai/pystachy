# error: boolean singleton patterns require a concrete bool or dynamic Any subject
def classify(value: int | bool | None) -> str:
    match value:
        case True:
            return "true"
        case False:
            return "false"
        case None:
            return "none"
        case _:
            return "other"


print(classify(True), classify(False), classify(None), classify(1))
