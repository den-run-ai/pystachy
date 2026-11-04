# error: a variadic positional must be last
import argparse

p = argparse.ArgumentParser()
p.add_argument("paths", nargs="*")
p.add_argument("output")
