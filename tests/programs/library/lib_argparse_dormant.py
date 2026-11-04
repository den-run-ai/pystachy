import argparse


def deferred(name):
    p = argparse.ArgumentParser()
    p.add_argument(name)
    return p.parse_args([])


print("unused parser definition")
