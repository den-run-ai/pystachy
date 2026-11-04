# Exercise both directions through the port's public CLI and process arguments.
import sys

import roman


def run_cli(args: list[str]) -> None:
    del sys.argv[1:]
    sys.argv.extend(args)
    print(roman.main())


run_cli(["1987"])
run_cli(["-r", "mcmlxxxvii"])
