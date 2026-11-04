# error: parser must be used in its declaring scope
import argparse


def configure() -> None:
    p.add_argument("path")


p = argparse.ArgumentParser()
configure()
