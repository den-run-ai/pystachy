# error: argparse schema: argument names must be distinct nonempty string literals
import argparse

p = argparse.ArgumentParser(prog="tool")
name = "--number"
p.add_argument(name)
