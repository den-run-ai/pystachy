# error: integer literal does not fit in 64 bits
import argparse

p = argparse.ArgumentParser()
p.add_argument("--value", type=int, choices=[0x1_0000_0000_0000_0000])
