import argparse

parser = argparse.ArgumentParser(prog="read", description="Read a file.")
parser.add_argument("name", help="file to read")
parser.add_argument("-n", "--number", type=int, help="number of lines")
parser.add_argument("--mode", choices=["text", "raw"], help="output format")
parser.parse_args(["-h"])
print("unreachable")
