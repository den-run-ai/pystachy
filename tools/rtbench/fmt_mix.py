n = 0
for i in range(600000):
    n += len(f"{i:>10,}") + len(f"{i * 0.5:.3f}") + len(f"{'ab':^7}") + len(f"{i:08x}") + len(f"{i / 7:e}")
print(n)
