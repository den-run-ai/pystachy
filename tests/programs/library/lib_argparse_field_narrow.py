# A test narrows an optional field of the Namespace that parse_args() returned to a function's
# local, where the function only reads the local's fields: nothing else can hold the Namespace.
import argparse


def show(path: str, count: int) -> str:
    return path + ":" + str(count)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="demo")
    parser.add_argument("filename", nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("-n", "--count", type=int)
    parser.add_argument("-r", "--ratio", type=float)
    parser.add_argument("--flag", action="store_true")
    parser.add_argument("--level", type=int, default=2)
    args = parser.parse_args(argv)
    if args.filename and args.output:
        print("both", show(args.filename, args.level), show(args.output, 0))
    if args.count is not None:
        print("count", args.count + 1)
    elif args.filename:
        print("file", show(args.filename, len(args.filename)))
    if args.ratio is not None and args.ratio > 0.5:
        print("ratio", args.ratio * 2)
    for _ in range(2):
        if args.filename is None:
            break
        print("loop", args.filename.upper())
    with_name = f"{args.filename}" if args.filename else "-"
    # (another scope reads the field itself)
    print(with_name, [args.level + i for i in range(2)], [o for o in [args.output] if o], args.output or args.filename or "nothing")
    try:
        if not args.output:
            print("no output", args.flag, args.output)
            return 1
    finally:
        print("checked", args.flag)
    print(show(args.output, args.count or -1), args.output.upper(), args.flag)
    return 0


def twice(argv: list[str]) -> None:
    # two Namespaces of one parser, each with its own fields
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output")
    first = parser.parse_args(argv)
    second = parser.parse_args([])
    if first.output:
        print("first", show(first.output, 1), second.output)
    if second.output is None and first.output is not None:
        print("second", first.output.lower())


def printed(argv: list[str]) -> None:
    # the Namespace itself is used: its fields are read as before, and a copy is tested
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output")
    args = parser.parse_args(argv)
    output = args.output
    if output:
        print(show(output, 3), args)


print(run(["in.json", "-o", "out.json"]))
print(run(["-n", "4", "-r", "0.75"]))
print(run(["x", "--flag"]))
print(run([]))
twice(["-o", "A.txt"])
twice([])
printed(["-o", "p"])
