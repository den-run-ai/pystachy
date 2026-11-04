import argparse as cli


def run() -> None:
    many = cli.ArgumentParser(prog="many")
    many.add_argument("--weight", type=float, default=0.5)
    many.add_argument("files", nargs="*")
    first = many.parse_args(["--weight", "1.25", "--", "one", "-two"])
    second = many.parse_args([])
    first.files.append("three")
    print(first.weight, first.files, second.weight, second.files)

    numbers = cli.ArgumentParser(prog="numbers")
    numbers.add_argument("items", type=int, nargs="+")
    result = numbers.parse_args(["-2", "3"])
    print(result.items)


run()
