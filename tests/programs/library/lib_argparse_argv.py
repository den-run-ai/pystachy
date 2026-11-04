import argparse

parser = argparse.ArgumentParser(prog="names")
parser.add_argument("first")
parser.add_argument("second")
args = parser.parse_args()
print(args.first, args.second)
