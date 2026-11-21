"""Native int text kernels: str(int) and int(str, base); the timed region excludes input construction."""
import sys
from time import perf_counter


def numbers(count: int, short: bool) -> list[int]:
    # ints of every length up to 19 digits and both signs, or of one to four digits
    out: list[int] = []
    x = 12345
    for i in range(count):
        x = (x * 1103515245 + 12345) % 2147483648
        v = (x * 2147483648 + i) >> (i % 62)
        if short:
            v %= 10000
        out.append(-v if i & 1 else v)
    return out


def write(n: int, values: list[int]) -> float:
    total = 0
    m = len(values)
    for i in range(n):
        s = str(values[i % m] ^ (i & 7))
        # Consume the length and the last byte written.
        total += len(s) + ord(s[len(s) - 1])
    return float(total)


def read(n: int, texts: list[str], base: int) -> float:
    total = 0
    m = len(texts)
    for i in range(n):
        total += int(texts[i % m], base) % 1009
    return float(total)


def spelled(values: list[int], base: int) -> list[str]:
    digits = "0123456789abcdef"
    out: list[str] = []
    for v in values:
        u = -v if v < 0 else v
        s = ""
        while True:
            s = digits[u % base] + s
            u //= base
            if u == 0:
                break
        out.append(("-" if v < 0 else "") + s)
    return out


kind = sys.argv[1]
n = int(sys.argv[2])
values = numbers(4096, kind.endswith("-short"))
texts: list[str] = []
if kind == "int-str" or kind == "int-str-short":
    texts = spelled(values, 10)
elif kind == "int-str-hex":
    texts = spelled(values, 16)
elif kind == "int-str-padded":
    texts = [" " + t + "\n" for t in spelled(values, 10)]

begin = perf_counter()
value = 0.0
if kind == "str-int" or kind == "str-int-short":
    value = write(n, values)
elif kind == "int-str-hex":
    value = read(n, texts, 16)
elif kind.startswith("int-str"):
    value = read(n, texts, 10)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - begin
print(value.hex(), elapsed)
