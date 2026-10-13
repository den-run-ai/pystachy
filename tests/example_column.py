# examples/column: aligned columns of a generated table, written into an io.StringIO with
# print(file=), as CPython prints them; then its errors, whose last line goes to stderr
import io
import os
import tempfile

import column
import gentable

rows = [["a", "bb", "ccc"], ["dddd", "e"], ["", "ffffff", "g", "h"], ["i"]]
print(column.widths(rows), column.widths([]), column.parse_columns("1,3,3"))
out = io.StringIO()
column.align(rows, "  ", set(), out)
column.align(rows, "|", {1, 3}, out)
print(out.getvalue(), end="")
print(repr(out.getvalue()[:12]), out.tell(), len(out.getvalue()))
for text in ["0", "a", "1,,2", ""]:
    try:
        column.parse_columns(text)
    except ValueError as e:
        print("ValueError:", e)

d = tempfile.mkdtemp()
path = os.path.join(d, "table.tsv")
with open(path, "w") as f:
    for i in range(40):
        f.write(gentable.row(i, "\t") + "\n")
    f.write("\n")
    f.write("short\trow\n")
csv = os.path.join(d, "table.csv")
with open(csv, "w") as f:
    for i in range(10):
        f.write(gentable.row(i, ",") + "\n")
for argv in [[path], ["-R", "1,5,6,7", path], ["-o", " | ", path], ["-s", ",", "-R", "2", csv]]:
    print(argv[:-1], "->", column.main(argv))
for argv in [["-R", "0", path], ["-s"], ["-s", "", path], ["-o"]]:
    print([a if a != path else "TABLE" for a in argv], "->", column.main(argv))
for p in [path, csv]:
    os.remove(p)
os.rmdir(d)
