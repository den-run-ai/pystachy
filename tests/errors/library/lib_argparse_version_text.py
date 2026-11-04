# error: argparse schema: version requires a literal string
import argparse

version = "tool 2.0"
p = argparse.ArgumentParser()
p.add_argument("--version", action="version", version=version)
