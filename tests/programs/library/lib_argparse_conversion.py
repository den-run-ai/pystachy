import argparse

parser = argparse.ArgumentParser(prog="convert")
parser.add_argument("-n", "--number", type=int)
parser.parse_args(["--number=1.5"])
print("unreachable")
