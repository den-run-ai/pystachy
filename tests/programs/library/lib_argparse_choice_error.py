import argparse

parser = argparse.ArgumentParser(prog="read")
parser.add_argument("--format", choices=["text", "raw"])
parser.parse_args(["--format", "json"])
print("unreachable")
