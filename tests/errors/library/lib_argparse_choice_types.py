# error: choices must match the converter
import argparse

p = argparse.ArgumentParser()
p.add_argument("--number", type=int, choices=[1, "2"])
