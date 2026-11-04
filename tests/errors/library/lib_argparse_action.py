# error: argparse schema: unsupported action append
import argparse

p = argparse.ArgumentParser(prog="tool")
p.add_argument("--item", action="append")
