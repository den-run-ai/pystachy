# error: argument 1 of need() may be None (str | None), and a test does not narrow a global or a field (a call may change it): copy it to a local variable, and test that
# A function that passes its Namespace on may have its fields changed by the call: a test of one
# narrows nothing, as for any object's field.
import argparse


def need(s: str) -> str:
    return s


def clear(ns: argparse.Namespace) -> None:
    pass


def run(argv: list[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output")
    args = parser.parse_args(argv)
    if args.output:
        clear(args)
        print(need(args.output))


run(["-o", "x"])
