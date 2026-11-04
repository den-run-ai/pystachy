# error: argparse schema: only direct declarations followed by supported parser methods are allowed
import argparse

p = argparse.ArgumentParser(prog="tool")
p.add_subparsers()
