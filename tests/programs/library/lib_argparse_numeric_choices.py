import argparse

p = argparse.ArgumentParser(prog="zero")
p.add_argument("--float", type=float, choices=[0.0])
p.add_argument("--count", type=int, choices=(-0, 0x10))
args = p.parse_args(["--float", "-0.0", "--count", "0"])
print(args.float, args.count)
