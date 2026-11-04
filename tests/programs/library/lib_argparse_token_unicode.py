import argparse

parser = argparse.ArgumentParser(prog="numbers")
parser.add_argument("-i", type=int)
parser.add_argument("-f", type=float)
parser.add_argument("names", nargs="*")
args, rest = parser.parse_known_args(["-i", "-١٢", "-f", "-.５", "-१", "-²", "-१_२"])
print(args, rest)
