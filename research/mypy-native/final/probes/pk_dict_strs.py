from typing import Final
class Specifier:
    _operators: Final = {
        "~=": "compatible",
        "==": "equal",
    }
    def op(self, s: str) -> str:
        return self._operators[s]
print(Specifier().op("=="))
