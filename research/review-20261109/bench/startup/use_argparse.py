import argparse
p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=3)
a = p.parse_args()
print(a.n)
