class EarlyClass:
    value = 11


def early_fn() -> int:
    return 12


early_value = 13

import from_ready_reader


class LateClass:
    value = 21


def late_fn() -> int:
    return 22


late_value = 23
print("source done")
