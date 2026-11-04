# error: argparse schema: default must be None or a scalar literal of the result type
import argparse

p = argparse.ArgumentParser(prog="tool")
default = 3
p.add_argument("--number", type=int, default=default)
