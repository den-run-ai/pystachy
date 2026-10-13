"""column: align the columns of a table, as column -t does, building the output in an io.StringIO.

usage: python3 column.py [-s SEP] [-o SEP] [-R COLS] [FILE...]
       pystachy build column.py -o column && ./column -s , data.csv

Each line is split at SEP (a tab by default) into cells, and each column is padded to its widest
cell; the cells of a line are joined by the output separator (two spaces by default), and the last
cell of a line is not padded. -R right-aligns the columns it names (1,3: numbered from 1). The
table is written into an io.StringIO, a line at a time with print(..., file=), then written out at
once. With no FILE, or for a FILE that is -, it reads standard input.
"""
import io
import sys


def widths(rows: list[list[str]]) -> list[int]:
    """The width of each column: its widest cell."""
    out: list[int] = []
    for row in rows:
        for i in range(len(row)):
            n = len(row[i])
            if i == len(out):
                out.append(n)
            elif n > out[i]:
                out[i] = n
    return out


def align(rows: list[list[str]], outsep: str, right: set[int], out: io.StringIO) -> None:
    """Write the rows into out, a line each, their columns aligned."""
    w = widths(rows)
    for row in rows:
        cells: list[str] = []
        last = len(row) - 1
        for i in range(len(row)):
            if i + 1 in right:
                cells.append(row[i].rjust(w[i]))
            elif i == last:
                cells.append(row[i])
            else:
                cells.append(row[i].ljust(w[i]))
        print(outsep.join(cells), file=out)


def parse_columns(text: str) -> set[int]:
    out: set[int] = set()
    for part in text.split(","):
        if not part.isdigit() or int(part) == 0:
            raise ValueError(f"invalid column number: {part!r}")
        out.add(int(part))
    return out


def main(argv: list[str]) -> int:
    sep = "\t"
    outsep = "  "
    right: set[int] = set()
    files: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-s", "-o", "-R"):
            if i + 1 == len(argv):
                print(f"column: option {arg} requires an argument", file=sys.stderr)
                return 2
            value = argv[i + 1]
            i += 2
            if arg == "-s":
                if value == "":
                    print("column: the separator must not be empty", file=sys.stderr)
                    return 2
                sep = value
            elif arg == "-o":
                outsep = value
            else:
                try:
                    right = parse_columns(value)
                except ValueError as e:
                    print(f"column: {e}", file=sys.stderr)
                    return 2
            continue
        files.append(arg)
        i += 1
    rows: list[list[str]] = []
    for name in files or ["-"]:
        f = sys.stdin if name == "-" else open(name)
        for line in f:
            text = line[:-1] if line.endswith("\n") else line
            if text != "":
                rows.append(text.split(sep))
        if name != "-":
            f.close()
    out = io.StringIO()
    align(rows, outsep, right, out)
    sys.stdout.write(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
