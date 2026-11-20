# Documented deviation (docs/language/typing.md#operations-on-closed-unions): value % number,
# where a closed union's value is a str that holds a conversion, raises TypeError: formatting
# with a format string computed at run time is not compiled. CPython prints "3 items" and then
# "ValueError incomplete format". A str without a conversion raises CPython's own TypeError,
# and a number takes the remainder.
import json


def show(text: str) -> None:
    value = json.loads(text)
    try:
        print(value % 3)
    except TypeError as e:
        print("TypeError", e)
    except ValueError as e:
        print("ValueError", e)


show('"%d items"')
show('"100%"')
show('"plain"')
show("10")
show("7.5")
