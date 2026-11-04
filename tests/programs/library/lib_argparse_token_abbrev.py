import argparse

parser = argparse.ArgumentParser(prog="forward", allow_abbrev=False)
parser.add_argument("-q", "--quiet", action="store_true")
parser.add_argument("-o", "--output")
parser.add_argument("files", nargs="*")
args, rest = parser.parse_known_args(["--qui", "--out=raw", "src", "--out=a b", "-qo", "one"])
print(args, rest)
print(parser.parse_args(["--quiet", "--output=a b", "--out name=x"]))

normal = argparse.ArgumentParser(prog="normal", allow_abbrev=True)
normal.add_argument("--output")
print(normal.parse_args(["--out=a b"]))
