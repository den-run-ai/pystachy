from mods.constructor_fixed import Count
import mods.constructor_fixed as fixed


def count(value: Count) -> int:
    return value.read()


print(count(Count([1, 2])), count(Count((3, 4))))
print(count(fixed.Count([5, 6])), count(fixed.Count((7, 8))))
print(isinstance(fixed.Count([9]), Count))
