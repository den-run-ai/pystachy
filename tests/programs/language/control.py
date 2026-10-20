import sys

LIMIT = 30
seen: list[int] = []


def collatz(n: int) -> int:
    steps = 0
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
    return steps


def classify(n: int) -> str:
    if n < 0:
        return "negative"
    elif n == 0:
        return "zero"
    elif n % 2 == 0:
        return "even"
    else:
        return "odd"


def record(x: int) -> None:
    global LIMIT
    seen.append(x)
    LIMIT -= 1


for i in range(10, 0, -3):
    record(i)
print(seen, LIMIT, [classify(x) for x in [-2, 0, 3, 8]], collatz(27))
for i in range(3):
    for j in range(3):
        if j == i:
            continue
        if i + j > 3:
            break
        print(i, j, end=" ")
print()
i = 0
while True:
    i += 1
    if i > 100:
        break
print(i)
x = 0
y = 5
s = ""
e = [0]
print(x or y, y or x, x and y, y and x, s or "default", "set" or s, e or [9])
print(not x, not y, not s, not "a", x < y and y < 10, x > y or y > 3)
print(1 if x else 2, "yes" if y > 3 else "no", (x or 7) + 1)
n = 6
print(n > 5 and n < 10, 0 < n < 10, not (n == 6))
total = 0
for k in range(100):
    if k % 3 == 0 or k % 5 == 0:
        total += k
print(total)
fz: list[str] = []
for k in range(1, 16):
    fz.append("FizzBuzz" if k % 15 == 0 else "Fizz" if k % 3 == 0 else "Buzz" if k % 5 == 0 else str(k))
print(" ".join(fz))
assert total == 2318, "sum mismatch"
count = 0
for _ in range(5):
    count += 1
print(count, _)


def early(xs: list[int]) -> int:
    for v in xs:
        if v > 10:
            return v
    return -1


print(early([1, 20, 30]), early([1, 2]))
if __name__ == "__main__":
    print("main block", len(sys.argv) >= 1)
