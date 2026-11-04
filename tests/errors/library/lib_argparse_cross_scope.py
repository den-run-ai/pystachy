# error: parser must be used in its declaring scope
import argparse

p = argparse.ArgumentParser()


def register() -> None:
    p.add_argument("path")


register()
