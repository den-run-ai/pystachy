"""Probe only: a gc stand-in, to see what follows `import gc` (not a proposal of semantics)."""


def collect(generation: int = 2) -> int:
    return 0


def enable() -> None:
    pass


def disable() -> None:
    pass


def isenabled() -> bool:
    return True


def get_threshold() -> tuple[int, int, int]:
    return (2000, 10, 0)


def set_threshold(threshold0: int, threshold1: int = 10, threshold2: int = 0) -> None:
    pass


def is_tracked(obj) -> bool:
    return False
