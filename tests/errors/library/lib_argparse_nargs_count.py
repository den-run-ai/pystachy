# error: argparse schema: nargs requires a literal string
import argparse

p = argparse.ArgumentParser(prog="tool")
p.add_argument("pair", nargs=2)
