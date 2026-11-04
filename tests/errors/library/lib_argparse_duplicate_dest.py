# error: argparse schema: duplicate destination value
import argparse

p = argparse.ArgumentParser(prog="tool")
p.add_argument("--value", type=int)
p.add_argument("--name", dest="value")
