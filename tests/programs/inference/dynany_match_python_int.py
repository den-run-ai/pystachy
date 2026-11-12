# pystachy: dynamic-any
# pystachy: python-int
from typing import Any


def classify(value: Any) -> str:
    match value:
        case True:
            return "true"
        case False:
            return "false"
        case None:
            return "none"
        case -9223372036854775808:
            return "minimum"
        case 18446744073709551616:
            return "large"
        case 1:
            return "one"
        case captured:
            return str(captured)


print(classify(True), classify(False), classify(None), classify(1), classify(1.0))
print(classify(-9223372036854775808), classify(18446744073709551616))
print(classify("text"), classify(18446744073709551617))
