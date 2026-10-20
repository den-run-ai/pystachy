# Result contexts also reach inherited templates and a bound method value.
class Rows:
    def pair(self, left, right):
        return [left, right]

    def nested(self, value):
        return ([], {"items": []})


class Derived(Rows):
    pass


factory = Derived()
numbers: list[int | float] = factory.pair(9007199254740993, 2.5)
print(numbers, isinstance(numbers[0], int), isinstance(numbers[1], float))
bound = factory.pair
mixed: list[int | str] = bound(7, "word")
print(mixed)
result: tuple[list[str], dict[str, list[int]]] = factory.nested(1)
result[0].append("nested")
result[1]["items"].append(8)
print(result)
