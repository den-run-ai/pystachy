from argparse import ArgumentParser


def run() -> None:
    parser = ArgumentParser(prog="tokenize")
    parser.add_argument(dest="filename", nargs="?", metavar="filename.py")
    print(parser.parse_args([]).filename, parser.parse_args(["main.py"]).filename)


run()
