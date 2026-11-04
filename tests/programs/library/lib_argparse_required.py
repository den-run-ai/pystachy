import argparse

parser = argparse.ArgumentParser(prog="take")
parser.add_argument("--number", type=int, required=True)
parser.add_argument("file")
parser.parse_args([])
print("unreachable")
