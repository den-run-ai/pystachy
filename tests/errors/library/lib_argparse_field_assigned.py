# error: argument 1 of need() may be None (str | None), and a test does not narrow a global or a field (a call may change it): copy it to a local variable, and test that
# A function that stores to a field of its Namespace reads the fields themselves: a test of one
# narrows nothing.
import argparse


def need(s: str) -> str:
    return s


def run(argv: list[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output")
    parser.add_argument("-i", "--input")
    args = parser.parse_args(argv)
    args.input = None
    if args.output:
        print(need(args.output))


run(["-o", "x"])
