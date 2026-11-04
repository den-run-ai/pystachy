import argparse

parser = argparse.ArgumentParser(prog="take")
parser.add_argument("-n", "--number", required=True, type=int)
parser.parse_args(["-n"])
print("unreachable")
