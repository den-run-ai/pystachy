# error: argparse schema: type must name the unshadowed builtin str, int or float
import argparse


def size(value: str) -> int:
    return len(value)


p = argparse.ArgumentParser(prog="tool")
p.add_argument("--size", type=size)
