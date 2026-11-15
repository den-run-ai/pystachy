# StrEnum's str payload is immutable even though its _value_ attribute can be
# reassigned. A declined comparison must fall back to that original payload.
from enum import StrEnum


class Text(StrEnum):
    FIRST = "alpha"
    ALIAS = "alpha"

    def __eq__(self, other) -> bool:
        return NotImplemented

    def __ne__(self, other) -> bool:
        return NotImplemented


member = Text.FIRST
print(member is Text.ALIAS, member.value)
print(member == "alpha", "alpha" == member, member != "alpha", "alpha" != member)
member._value_ = "changed"
print(member.value)
print(member == "alpha", "alpha" == member, member != "alpha", "alpha" != member)
print(member == "changed", "changed" == member, member != "changed", "changed" != member)
