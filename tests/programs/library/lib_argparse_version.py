import argparse

p = argparse.ArgumentParser(prog="tool", add_help=False)
p.add_argument("-v", action="store_true")
p.add_argument("-V", "--version", action="version", version="%(prog)s  1.2 (100%%)")
p.add_argument("version", nargs="?", default="latest")
print(p.parse_args([]))
print(p.parse_known_args(["-v", "stable", "--later"]))
p.print_help()
p.parse_args(["-vV"])
print("unreachable")
