# examples/cut: cut.py's options, parsed by getopt.gnu_getopt, its ranges, and the lines it prints
# for a generated table, as CPython prints them; then its errors, whose last line goes to stderr
import os
import tempfile

import cut
import gentable

for text in ["1,3-5,7-", "5,1-2,2-3", "-3", "4-", "2,2,2", "9-12,3", "1-1"]:
    print(text, cut.parse_list(text))
for text in ["1099511627777-", "999999999999999999-", "3-999999999999999999"]:
    print(text, cut.parse_list(text), cut.cut_line("a\tb", cut.parse_list(text), True, "\t", "\t", False, False))
for text in ["", "0", "3-1", "a", "1,,2", "-", "1-2-3", "1000000000000000000", "2-1000000000000000000"]:
    try:
        cut.parse_list(text)
    except ValueError as e:
        print(repr(text), "ValueError:", e)
print(cut.select(["a", "b", "c", "d", "e"], cut.parse_list("2,4-"), False), cut.select(["a", "b", "c", "d", "e"], cut.parse_list("2,4-"), True))
print(cut.select(["a", "b"], cut.parse_list("3-"), False), cut.select(["a", "b"], cut.parse_list("3-"), True), cut.select([], cut.parse_list("1"), True))

d = tempfile.mkdtemp()
path = os.path.join(d, "table.tsv")
with open(path, "w") as f:
    for i in range(60):
        f.write(gentable.row(i) + "\n")
    f.write("no newline\tat the end")
for argv in [["-f", "2,5-7"], ["-f", "3", "--complement"], ["-c", "1-12"], ["-s", "-f", "8,1"],
             ["--fields=-2,7-", "--output-delimiter=|"], ["-f", "4", "-d", "e"], ["--compl", "-f1-3,5"]]:
    print(argv, "->", cut.main(argv + [path]))
print(cut.main([path, "-f", "1", "-d", "#", "--only-delimited"]))
print(cut.main(["--help"]))
for argv in [["-x"], ["-f", "0"], ["-f", "3-1"], ["-c", "2", "-s"], ["-d", "ab", "-f", "1"], ["-f"], ["--fields"], [],
             ["-f", "1", "-f", "2"], ["-f", "1", "-c", ""], ["-c", ""], ["--fields=1", "-c", "1"]]:
    print(argv, "->", cut.main(argv + [path]))
os.remove(path)
os.rmdir(d)
