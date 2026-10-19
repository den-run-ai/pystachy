# A template's local display of an int and a float, mutated, then returned: a list of their
# union.
def indirect(a, b):
    result = [a, b]
    result.append(a)  # A mutated local is outside fresh-result forwarding.
    return result


result: list[int | float] = indirect(1, 2.5)
print(result)
