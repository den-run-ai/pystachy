# error: argparse schema: only direct declarations followed by supported parser methods are allowed
import argparse
import sys

p = argparse.ArgumentParser(prog="tool")
if len(sys.argv) > 1:
    p.add_argument("--number", type=int)
