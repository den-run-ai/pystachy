# pystachy: python-int
import argparse

parser = argparse.ArgumentParser(prog="size")
parser.add_argument("--size", type=int)
args = parser.parse_args(["--size", "123456789012345678901234567890"])
missing = parser.parse_args([])
print(args.size, missing.size)
