# string processing and dict-heavy word counting
def make_text(n: int) -> str:
    words = ["lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", "sed", "do"]
    parts: list[str] = []
    seed = 12345
    for i in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        w = words[seed % len(words)]
        parts.append(w + str(seed % 97) if seed % 7 == 0 else w)
    return " ".join(parts)


text = make_text(400000)
counts: dict[str, int] = {}
for w in text.split(" "):
    counts[w] = counts.get(w, 0) + 1
top = sorted([(-c, w) for w, c in counts.items()])[:5]
print(len(counts), top)
caps = 0
for w in text.split():
    if w.upper().startswith("L"):
        caps += 1
print(caps, len(text))
