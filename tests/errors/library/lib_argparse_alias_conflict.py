# error: duplicate option --help
import argparse

p = argparse.ArgumentParser()
p.add_argument("--help", action="store_false")
