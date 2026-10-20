# A module whose code ends, after it imports side (tests/programs/imports/import_try_binding*.py)
import side

print("good: init")
A = 1


def A2() -> int:
    return 2


class K:
    v: int = 3
