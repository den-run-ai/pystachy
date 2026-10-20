# error: got list[int]
# Expected result contexts do not reinterpret a method's populated list.
class Factory:
    def items(self, value):
        items = [value]
        return items


result: list[str] = Factory().items(1)
