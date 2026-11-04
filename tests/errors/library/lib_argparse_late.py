# error: argparse schema: add_argument must precede parsing
import argparse

p = argparse.ArgumentParser(prog="tool")
p.add_argument("first")
p.parse_args(["one"])
p.add_argument("second")
