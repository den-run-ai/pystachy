from mods.alias_base import Box, inc


def build() -> int:
    return Crate(12).v


def invoke() -> int:
    return plus(12)


def through_import() -> int:
    import mods.alias_ready_cycle_a as same
    return same.plus(8)


import mods.alias_ready_cycle_b

Crate = Box
plus = inc
also = plus
