from mods.constructor_fixed import Adjusted, Count
import mods.constructor_fixed as fixed


def count(value: Count) -> int:
    return value.read()


print(count(Count([1, 2])), count(Count((3, 4))))
print(count(Adjusted([5, 6])), count(fixed.Adjusted((7, 8))))
print(isinstance(fixed.Adjusted([9]), Count))
print(count(fixed.Converted("10")), count(fixed.Converted(11)))
