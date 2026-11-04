from argparse import ArgumentParser


def run() -> None:
    first = ArgumentParser(prog="tool")
    first.add_argument("--value", type=int)
    second = ArgumentParser(prog="flags")
    second.add_argument("--disable", dest="value", action="store_false")
    first_args = first.parse_args(["--value", "5"])
    second_args = second.parse_args(["--disable"])
    default_args = first.parse_args([])
    print(first_args.value, second_args.value, default_args.value)


run()
