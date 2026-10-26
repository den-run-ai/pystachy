import timeit
def text(digits, salt):
    s = [str((i * 7 + salt + i // 13) % 10) for i in range(digits)]
    s[0] = "9"
    return "".join(s)
for op, digits, n in [("add", 4200, 200000), ("sub", 4200, 200000), ("add", 128, 2000000), ("mul", 640, 50000),
                      ("mul", 1000, 20000), ("mul", 4200, 2000), ("sqr", 640, 50000), ("sqr", 4200, 2000),
                      ("lop", 4200, 3000), ("div", 4200, 3000)]:
    a, b, small = int(text(digits, 1)), int(text(digits, 5)), int(text(digits // 3 + 1, 3))
    stmt = {"add": "a + b", "sub": "a - b", "mul": "a * b", "sqr": "a * a", "lop": "a * small", "div": "a // small"}[op]
    best = min(timeit.repeat(stmt, globals={"a": a, "b": b, "small": small}, number=n, repeat=7)) / n * 1e6
    print(f"{op:4s} {digits:6d} digits: CPython {best:10.3f} us")
