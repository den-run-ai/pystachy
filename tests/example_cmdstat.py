# examples/cmdstat: a generated shell history's lines split by lib/shlex into commands, counted and
# rejoined with shlex.join(), as CPython splits, counts and joins them; then its errors, whose last
# line goes to stderr
import os
import tempfile

import cmdstat
import gencmds

for text in ["ls -la", "a | b | c && d", "grep -n 'x y' < in > out 2>&1", "(cd src && make) ; echo done",
             "echo '|' \"&&\"", "a>b", "x||y|z", "cat <<EOF", "", "   ", "\"\"", "do \\; this", "f 2>/dev/null|g"]:
    tokens = cmdstat.split_line(text)
    print(repr(text), tokens, [cmdstat.kind(t) for t in tokens], cmdstat.commands(tokens))
for text in ['echo "open', "echo 'open", "trailing \\"]:
    try:
        cmdstat.split_line(text)
    except ValueError as e:
        print(repr(text), "ValueError:", e)
lines = [gencmds.line(i) for i in range(1000)]
print(lines[0], "|", lines[499])
total = 0
for text in lines:
    try:
        cmds, longest, redirects = cmdstat.commands(cmdstat.split_line(text))
    except ValueError:
        continue
    total += len(cmds) * 1000 + longest * 10 + redirects
print(total)

d = tempfile.mkdtemp()
path = os.path.join(d, "history.txt")
with open(path, "w") as f:
    for text in lines:
        f.write(text + "\n")
    f.write("last line without a newline 'quoted words'")
for argv in [["--top", "5"], ["--top", "0"], []]:
    print(argv, "->", cmdstat.main(argv + [path]))
print(cmdstat.main(["--quote", path]))
for argv in [["--top"], ["-x", path], [], [path, path]]:
    print([a.replace(d, "D") for a in argv], "->", cmdstat.main(argv))
os.remove(path)
os.rmdir(d)
