def steps(k: int) -> int:
    total = 0
    for i in range(10, 0, k):
        total += i
    return total


print(steps(-3), steps(4))
print(steps(0))
