# pystachy: dynamic-any
from typing import Any, Callable
import templateboxes
import typechecks


# The helpers do not opt in. Their parameter specializations must compare the
# same Python classes as opted-in code, without selecting a payload layout.
def check(value: Any) -> None:
    typechecks.exact(value)


def pair(left: Any, right: Any) -> None:
    typechecks.same(left, right)


check(None)  # Compile the helpers before discovering boxed specializations.
number: Any = templateboxes.Box(7)
text: Any = templateboxes.Box("text")
items = [3, 4]
listed: Any = templateboxes.Box(items)
check(number)
check(text)
check(listed)
check(typechecks.Box(1))
check(templateboxes.Box)
check(typechecks.Base())
check(typechecks.Child())
check(1)
check("text")
pair(number, text)
pair(text, listed)
pair(number, typechecks.Box(1))
pair(None, number)
pair(typechecks.Base(), typechecks.Child())
pair([1], ["text"])
pair(1, True)


def increment(value: int) -> int:
    return value + 1


# Membership must not ask unrelated values for unsupported reflection results.
callback: Callable[[int], int] = increment
check(callback)

# Keep typed generic helpers and mixed typed/Any operands on the same contract.
typechecks.exact(templateboxes.Box(8))
typechecks.same(number, templateboxes.Box(9))
typechecks.same(templateboxes.Box("typed"), number)
typechecks.ordered(number, text)


class Factory:
    def make(self):
        return templateboxes.Box(1.5)


# Dispatch can discover another physical specialization after both helpers.
factory: Any = Factory()
late = factory.make()
check(late)
pair(number, late)
typechecks.append(listed)
print(listed.value is items, items)
