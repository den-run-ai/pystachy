# error: object has no attribute 'unknown'
import argparse

p = argparse.ArgumentParser(prog="tool")
p.add_argument("--name")
args = p.parse_args([])
print(args.unknown)
