# Imported decorated functions keep their Python names, inside the decorator and afterwards:
# module qualification is internal, and functools.wraps and nested closures use the same names.
import mods.decorator_names as names
from mods.decorator_names import greet as alias, inspect


@inspect
def main_fn() -> int:
    return 7


print(alias.__name__, alias.__qualname__, alias())
print(names.add.__name__, names.add.__qualname__, names.add(2))
nested = names.make()
print(nested.__name__, nested.__qualname__, nested())
print(main_fn.__name__, main_fn.__qualname__, main_fn())
