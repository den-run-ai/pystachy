# error: recursive_alias_compare_message.py:13: error: cannot compare list[JSONValue] == list[Box]
# A message that spells out its types names a recursive alias, here an imported one, as the
# program does, not as the compiler's internal edge type.
import json


class Box:
    def __init__(self, n: int) -> None:
        self.n = n


def main(values: list[json.JSONValue], boxes: list[Box]) -> None:
    print(values == boxes)


main([1, "a"], [Box(1)])
