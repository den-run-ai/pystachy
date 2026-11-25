class Stack(list[int]):
    pass

class Holder:
    def __init__(self) -> None:
        self.values: list[list[int]] = [[-1]]

holder = Holder()
old = holder.values
replacement: list[list[int]] = [[0]]

def get_holder() -> Holder:
    return holder

setattr(holder, "values", replacement)

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        holder.values.append(other)
        return len(other) == 1

print(Probe() == Stack([1]))
print(holder.values is replacement, old is holder.values)
print(old, holder.values)
