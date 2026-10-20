# error: @dataclass(slots=...) is not supported: its supported arguments are init=, repr=, eq=, order=, unsafe_hash=, frozen=, match_args=, kw_only=
from dataclasses import dataclass


@dataclass(slots=True)
class P:
    x: int
