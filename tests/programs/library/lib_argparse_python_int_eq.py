# pystachy: python-int
import argparse

p = argparse.ArgumentParser(prog="first")
p.add_argument("--size", type=int, default=0)
p.add_argument("--verbose", action="store_true")
p.add_argument("--name")
q = argparse.ArgumentParser(prog="second")
q.add_argument("--name")
q.add_argument("--verbose", action="store_true")
q.add_argument("--size", type=int, default=0)
r = argparse.ArgumentParser(prog="partial")
r.add_argument("--size", type=int)

a = p.parse_args(["--size", "123456789012345678901", "--verbose"])
b = q.parse_args(["--verbose", "--size", "123456789012345678901"])
short = r.parse_args(["--size", "123456789012345678901"])
print(a == b, b == a, a == short, short == a)
b.name = "changed"
print(a == b, a != b)
same_short = r.parse_args(["--size", "123456789012345678901"])
print(short == same_short)
