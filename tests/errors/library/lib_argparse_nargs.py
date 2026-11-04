# error: nargs supports positional
import argparse

p = argparse.ArgumentParser(prog="tool")
p.add_argument("--pair", nargs="?")
