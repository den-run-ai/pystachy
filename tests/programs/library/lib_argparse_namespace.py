import argparse


def run() -> None:
    parser = argparse.ArgumentParser(prog="collect")
    parser.add_argument("-n", "--number", type=int, default=3)
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--mode", choices=["fast", "exact"], default="fast")
    parser.add_argument("filename", nargs="?")

    first = parser.parse_args(["--number=-7", "-q", "--mode", "exact", "--", "-dash"])
    saved = first
    second = parser.parse_args([])
    print(first is saved, first is second)
    print(first == saved, first == second, isinstance(first, argparse.Namespace), repr(first))
    print(saved.number, saved.quiet, saved.mode, saved.filename)
    print(second.number, second.quiet, second.mode, second.filename)
    known, extras = parser.parse_known_args(["-n", "8", "file", "--plugin", "payload"])
    print(known.number, known.filename, extras)


run()
