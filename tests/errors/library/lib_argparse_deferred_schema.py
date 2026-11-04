# error: argument names must be distinct nonempty string literals
import argparse


def deferred(name):
    p = argparse.ArgumentParser()
    p.add_argument(name)
    return p.parse_args([])


deferred("file")
