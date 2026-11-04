# error: allow_abbrev must be a literal bool
import argparse

abbreviate = False
parser = argparse.ArgumentParser(allow_abbrev=abbreviate)
