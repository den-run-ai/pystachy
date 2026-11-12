from typing import Final
class R:
    control_fixer: Final = str.maketrans("".join(chr(i) for i in range(32) if i != 9), "?" * 31)
print("a\x01b\tc".translate(R.control_fixer))
