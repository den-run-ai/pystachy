s = "Hello, World"
print(s, len(s), s[0], s[-1], s[7:], s[:5], s[-5:-1], s[3:100], s[100:], s[:], s[8:3] == "")
print(s.upper(), s.lower(), s.find("o"), s.find("o", 5), s.find("xyz"), s.rfind("o"), s.index("W"), s.count("l"))
print(s.startswith("Hell"), s.startswith("World", 7), s.endswith("World"), s.replace("l", "L"), s.replace("", "-")[:7])
print("a,b,,c".split(","), "  lots   of\tspace \n".split(), "x".split(","), ",".join(["a", "b", "c"]), "".join([]))
print("[" + "  pad  ".strip() + "]", "[" + "xxhixx".strip("x") + "]", "[" + "  l".lstrip() + "]", "[" + "r  ".rstrip() + "]")
print("123".isdigit(), "12a".isdigit(), "".isdigit(), "abc".isalpha(), "ab1".isalnum(), " \t".isspace(), "ABC".isupper(), "abC".islower())
print("ab".ljust(5) + "|", "ab".rjust(5) + "|", "-" * 10, 3 * "ab", "x" * 0 + "!")
print("lo" in s, "LO" in s, "" in s, "z" not in s)
print("apple" < "banana", "apple" < "apple pie", "b" > "abc", "same" == "same", "a" != "b", "Z" < "a")
print(ord("A"), chr(97), chr(ord("a") + 25), str(42), str(-3.5), str(True), repr("it's"), repr('say "hi"'), repr("both ' \""))
print(repr("tab\there\nnewline\\back\x01"), "esc: \x41\101\t|")
t = ""
for ch in "abc":
    t = ch + t
print(t, list("xyz"), sorted("hello"), max("hello"), min(["pear", "apple", "fig"]))
name = "Ouro"
n = 3
pi = 3.14159265
print(f"{name} has {n} letters? {len(name) == 4} {{braces}} {name!r} {n * 2 + 1}")
print(f"[{n:5}] [{n:<5}] [{n:^5}] [{n:05}] [{-n:05}] [{n:+}] [{1234567:,}] [{255:x}] [{255:X}] [{8:o}]")
print(f"[{pi:.2f}] [{pi:10.3f}] [{pi:<10.1f}] [{pi:e}] [{pi:.3e}] [{0.5:%}] [{0.123:.1%}] [{pi:g}] [{1e20:g}]")
print(f"[{name:>8}] [{name:<8}] [{name:^8}] [{name:*^9}] [{name:.2}] [{2.0:.3}] [{1.5:8}] [{True}] [{[1, 2]}]")
print(f"{'nested ' + name}", f"{s[0:5]}", f"{3 != 4}", f"{n if n > 2 else -n}")
words = "the quick brown fox jumps over the lazy dog".split()
counts: dict[str, int] = {}
for w in words:
    counts[w] = counts.get(w, 0) + 1
print(counts, len(words), " ".join(sorted(words)))
lines = """first
second
third"""
print(lines.split("\n"), len(lines))
acc: list[str] = []
for i in range(5):
    acc.append(str(i * i))
print("+".join(acc), int("+".join(acc).replace("+", "")) % 97)
