from mods.constructor_hierarchy import Total, Bonus as Alias
import mods.constructor_hierarchy as models


def score(value: Total) -> int:
    return value.score()


def make(values):
    return Alias(values, "9")


# The first call compiles before the factory discovers the subclass. The later
# activation must rebuild this dispatch, while Invalid and InvalidChild stay lazy.
print(score(Total([1, 2])))
print(score(make((3, 4))))
print(score(models.Inherited([8, 9])))
print(score(models.Bonus([10])))
print(type(Alias([1])) is type(models.Bonus((2, 3))))
