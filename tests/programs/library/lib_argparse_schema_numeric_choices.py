# pystachy: python-int
import argparse


def parsed(str: int) -> None:
    parser = argparse.ArgumentParser(prog="numeric")
    parser.add_argument("--value", type=int, choices=[000, -0x1_0000_0000_0000_0000,
                                                        0x1_0000_0000_0000_0001])
    print(parser.format_usage(), end="")
    for value in ["0", "-18446744073709551616", "18446744073709551617"]:
        print(parser.parse_args(["--value", value]).value)


parsed(0)
