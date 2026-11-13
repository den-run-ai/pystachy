from from_kept_source import Pending, pending, value


def use() -> int:
    return Pending.value + pending() + value
