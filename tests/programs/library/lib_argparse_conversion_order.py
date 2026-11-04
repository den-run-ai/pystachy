import argparse

p = argparse.ArgumentParser(prog="items")
p.add_argument("values", nargs="+", type=int, choices=[1, 2])
p.parse_args(["3", "no"])
