class Stack(list[int]):
    pass

class Holder:
    def __init__(self) -> None:
        self.values: list[list[int]] = [[-1]]

holder = Holder()
old = holder.values
replacement: list[list[int]] = [[0]]

def get_holder() -> Holder:
    print("receiver")
    return holder

def make_item() -> list[int]:
    print("rhs")
    return [0]

get_holder().values = [make_item()]
setattr(get_holder(), "values", [make_item()])

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        holder.values.append(other)
        return isinstance(other, Stack)

print(Probe() == Stack([1]))
print(old is holder.values)
print(old, holder.values)
