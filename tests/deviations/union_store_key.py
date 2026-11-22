# Documented deviation (docs/language/typing.md#operations-on-closed-unions): an item assigned
# through a closed union's value raises TypeError where the value is a dict whose keys have
# another type than the index, where CPython adds the key (here it would print {'a': 1, 0: 'zero'}
# and nothing else): the dict's layout holds keys of one type. A list in the same variable takes
# the int index, so the assignment compiles.
import json


def put(text: str) -> None:
    value = json.loads(text)
    try:
        value[0] = "zero"
    except TypeError as e:
        print("TypeError", e)
    print(value)


put('{"a": 1}')
put("[1, 2]")
