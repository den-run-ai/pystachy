# error: parser must be used in its declaring scope
import argparse

p = argparse.ArgumentParser()


def configure(parser=p) -> None:
    parser.add_argument("path")


configure()
