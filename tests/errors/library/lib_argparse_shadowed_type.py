# error: type must name the unshadowed builtin str, int or float
from argparse import ArgumentParser


def convert(int: str) -> None:
    p = ArgumentParser()
    p.add_argument("--size", type=int)


convert("string")
