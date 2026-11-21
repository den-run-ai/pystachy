values = []
values.append(1)
values.append("a")
print(values)


def build(n: int):
    items = []
    items.append(n)
    for i in range(n):
        items.insert(0, str(i))
    items.extend([False])
    items += [None]
    items[0] = "first"
    return items


items = build(3)
alias = items
alias.append("tail")
print(items)


def interleave(n: int):
    left = []
    right = []
    a = "a"
    left.append(n)
    right.append(a)
    for i in range(n):
        if i == 2:
            break
        right.append(i)
        left.append(a)
    return left, right


print(interleave(3))
