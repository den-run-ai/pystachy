# Character classes of every shape the compiler makes of them (one or two runs, a 256-entry
# bitmap, a BMP table of chunks, items past the BMP), matched at the edges of each run and chunk.
import re


class Rng:
    def __init__(self, seed: int) -> None:
        self.s = seed

    def next(self, n: int) -> int:
        self.s = (self.s * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFF
        return (self.s >> 16) % n


ZONES = [(0, 128), (0, 256), (128, 256), (256, 0x3000), (0, 65536), (0xFF00, 65536), (65536, 0x20000),
         (0, 0x110000), (250, 262), (65530, 65542), (0, 64), (30, 34)]


def lit(c: int) -> str:
    if c < 256:
        return "\\x%02x" % c
    if c < 65536:
        return "\\u%04x" % c
    return "\\U%08x" % c


def code(r: Rng) -> int:
    z = ZONES[r.next(len(ZONES))]
    c = z[0] + r.next(z[1] - z[0])
    if 0xD800 <= c < 0xE000:
        c -= 0x800
    return c


def edges(out: list[int], c: int) -> None:
    for d in [-1, 0, 1]:
        if 0 <= c + d < 0x110000 and not 0xD800 <= c + d < 0xE000:
            out.append(c + d)


def main() -> None:
    r = Rng(2026)
    total = 0
    for i in range(360):
        parts: list[str] = []
        probes: list[int] = [0, 31, 32, 255, 256, 65535, 65536]
        if r.next(5) == 0:
            parts.append("^")
        for _ in range(1 + r.next(9)):
            k = r.next(12)
            if k < 6:
                c = code(r)
                parts.append(lit(c))
                edges(probes, c)
            elif k < 10:
                a = code(r)
                b = code(r)
                if a > b:
                    t = a
                    a = b
                    b = t
                if r.next(3) == 0:
                    b = min(a + r.next(600), 0x10FFFF)
                    if 0xD800 <= b < 0xE000:
                        b = 0xD7FF if a < 0xD800 else 0xE000
                parts.append(lit(a) + "-" + lit(b))
                edges(probes, a)
                edges(probes, b)
                edges(probes, (a + b) // 2)
                edges(probes, (a | 255) + 1)
            elif k == 10:
                parts.append(["\\w", "\\d", "\\s", "\\W", "\\D", "\\S"][r.next(6)])
                probes.extend([48, 65, 95, 0xE9, 0x660, 0x3000])
            else:
                c = code(r)
                d = code(r) % 256
                parts.append(lit(c) + lit(d))
                edges(probes, c)
                edges(probes, d)
        cls = "[" + "".join(parts) + "]"
        flags = 0
        if i % 17 == 0:
            flags = re.IGNORECASE
        elif i % 23 == 0:
            flags = re.ASCII
        p = re.compile(cls, flags)
        h = 0
        for c in probes:
            hit = p.fullmatch(chr(c)) is not None
            h = (h * 31 + (2 if hit else 1) * (c + 7)) & 0xFFFFFFFFFFFF
        total = (total * 1000003 + h) & 0xFFFFFFFFFFFF
        if i % 30 == 0:
            print(i, len(cls), int(flags), h)
    print("total", total)
    # the same set optimized for a pattern's start and in place, in patterns compiled one after another
    for pattern in [r"[{\[(#/]", "[{\\[(#/\"'“”]", r"[a-cx-z0-9_]+", r"[^\x00-\x7f\x81-\xff]", r"[\x00\x02Ą]x", r"[a\U00010000]"]:
        q = re.compile(pattern)
        print(ascii(pattern), [ascii(m) for m in q.findall("a{[(#/\"'“”x_9\x80\x00\x02Ąx\U00010000")])


main()
