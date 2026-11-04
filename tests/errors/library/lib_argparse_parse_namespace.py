# error: parse accepts only an optional argv
import argparse

p = argparse.ArgumentParser()
p.parse_args([], namespace=None)
