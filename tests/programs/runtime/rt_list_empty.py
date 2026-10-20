# Clearing keeps list identity and aliases. Every way to empty/reuse a list remains safe;
# copy, slices and self-extension also exercise zero-byte copies of detached backing storage.
def reuse(how: int) -> None:
    xs = list(range(16))
    alias = xs
    if how == 0:
        xs.clear()
    elif how == 1:
        xs *= 0
    elif how == 2:
        xs *= -3
    elif how == 3:
        while xs:
            xs.pop()
    elif how == 4:
        while xs:
            del xs[-1]
    else:
        while xs:
            xs.remove(xs[-1])
    print(how, xs is alias, alias, xs.copy(), xs[:], xs[10:20], xs + xs, xs * 4)
    xs.clear()
    xs.extend(xs)
    xs += alias
    xs.sort()
    xs.reverse()
    xs.insert(5, 3)
    xs.append(7)
    xs.extend(xs)
    print(alias, xs is alias, xs.pop(0), alias)
    alias.clear()
    xs += [9]
    xs *= 3
    print(xs, alias)


for k in range(6):
    reuse(k)


# clear() during sort must preserve the untouched sentinel, but append-then-empty must
# still be reported as a mutation even though the comparison leaves the list empty again.
mode = 0


class Item:
    def __init__(self, value: int):
        self.value = value

    def __lt__(self, other: "Item") -> bool:
        global target
        if mode == 0:
            target.clear()
            target.extend(target)
        else:
            target.append(Item(9))
            if mode == 1 or mode == 5:
                target.clear()
                if mode == 5:
                    raise RuntimeError("comparison")
            elif mode == 2:
                target.pop()
            elif mode == 3:
                del target[0]
            else:
                target *= 0
        return self.value < other.value


target: list[Item] = []


for mode in range(6):
    target = [Item(3), Item(1), Item(2)]
    try:
        target.sort()
        print("sorted", mode)
    except ValueError as e:
        print(mode, str(e))
    except RuntimeError as e:
        print(mode, str(e))
    print([item.value for item in target])
