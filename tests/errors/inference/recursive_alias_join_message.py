# error: recursive_alias_join_message.py:10: error: sequence item 0: expected str instance, V found
# Diagnostics name a recursive alias as the program does, not as the compiler's internal edge
# type. join() needs str items here, as it does for a union without a recursive alias.
type V = str | list[V]


def main(items: list[V]) -> None:
    for item in items:
        print(item)
    print("-".join(items))


main(["a", "b"])
