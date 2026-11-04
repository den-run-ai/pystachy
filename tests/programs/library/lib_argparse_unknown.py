import argparse

parser = argparse.ArgumentParser(prog="find")
parser.add_argument("name")
parser.parse_args(["file", "--plugin", "abc"])
print("unreachable")
