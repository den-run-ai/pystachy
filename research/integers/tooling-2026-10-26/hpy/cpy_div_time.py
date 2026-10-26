import timeit
def text(digits, salt):
    s = [str((i * 7 + salt + i // 13) % 10) for i in range(digits)]
    s[0] = "9"
    return "".join(s)
for op, digits, n in [("div", 4200, 3000), ("mod", 4200, 3000), ("div", 640, 100000), ("div", 160, 1000000), ("dig", 4200, 30000), ("div1", 4200, 300000)]:
    a, b, small = int(text(digits, 1)), int(text(digits, 5)), int(text(digits // 3 + 1, 3))
    stmt = {"div": "a // small", "mod": "a % small", "dig": "a // 1000000007", "div1": "a // b"}[op]
    best = min(timeit.repeat(stmt, globals={"a": a, "b": b, "small": small}, number=n, repeat=7)) / n * 1e6
    print(f"{op:4s} {digits:6d} digits: CPython {best:10.3f} us")
