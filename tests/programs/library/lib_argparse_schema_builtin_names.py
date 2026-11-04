import argparse

# These names belong to the application. The parser still produces native
# str, bool, and list fields and uses the builtin repr for a Namespace.
def str():
    return "app"

def repr():
    return "repr"

def int():
    return 17

def list():
    return 27

def bool():
    return 37

parser = argparse.ArgumentParser(prog="app")
parser.add_argument("--quiet", action="store_true")
parser.add_argument("names", nargs="*")
print(parser.parse_args(["--quiet", "Ada", "Jo"]))
print(str(), repr(), int(), list(), bool())
