# writelines() of str | None items writes them in order, until one that is None raises
import sys

xs: list[str | None] = ["a\n", None, "b\n"]
sys.stdout.writelines(xs)
