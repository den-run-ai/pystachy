"""Writes records.toml: 3,000 [[records]] tables with mixed field types (deterministic)."""
import random

r = random.Random(7)
out = ['title = "bench"', 'version = 3', '']
for i in range(3000):
    out.append("[[records]]")
    out.append(f"id = {i}")
    out.append(f'name = "item-{i}-{r.randrange(1000)}"')
    k = r.random()
    if k < 0.9:
        out.append(f"amount = {r.randrange(-1000, 100000)}")
    elif k < 0.97:
        out.append(f"amount = {r.random() * 1000:.3f}")
    else:
        out.append('amount = "n/a"')
    out.append(f"active = {'true' if r.random() < 0.5 else 'false'}")
    out.append(f"tags = [{', '.join(repr('t' + str(r.randrange(20))).replace(chr(39), chr(34)) for _ in range(r.randrange(4)))}]")
    out.append(f"point = {{ x = {r.randrange(100)}, y = {r.random():.4f} }}")
    if r.random() < 0.2:
        out.append(f"when = 2026-10-{1 + r.randrange(28):02d}T12:{r.randrange(60):02d}:00Z")
    out.append("[records.meta]")
    out.append(f'owner = "u{r.randrange(50)}"')
    out.append(f"score = {r.random():.6f}")
    out.append("")
open("records.toml", "w").write("\n".join(out))
