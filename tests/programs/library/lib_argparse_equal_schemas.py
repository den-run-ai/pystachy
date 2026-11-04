from argparse import ArgumentParser

p = ArgumentParser()
p.add_argument("--value", type=int)
q = ArgumentParser()
q.add_argument("--value", type=int)
a = p.parse_args(["--value", "1"])
b = p.parse_args(["--value", "2"])
c = q.parse_args(["--value", "1"])
print(a == b, a == c, a != b, a != c)
print(a, repr(b))
