# examples/linediff: unified and word diffs of two generated versions of a text, through difflib's
# SequenceMatcher, as CPython prints them; then its errors, whose last line goes to stderr
import os
import tempfile

import gentext
import linediff

print(linediff.span(0, 0), linediff.span(3, 4), linediff.span(3, 9), linediff.span(5, 5))
print(linediff.groups([("equal", 0, 10, 0, 10), ("replace", 10, 11, 10, 12), ("equal", 11, 30, 12, 31), ("delete", 30, 31, 31, 31)], 3))
print(linediff.groups([("equal", 0, 5, 0, 5)], 3), linediff.groups([], 3))
print(linediff.marked("the quick brown fox".split(), "the slow brown dog jumps".split(), [0, 0, 0, 0, 0], 1))
print(linediff.marked("a b c d".split(), "a x c d e".split(), [0, 1, 1, 2, 2], 4))
print(linediff.unified(["a\n", "b\n", "c\n"], ["a\n", "c\n", "d\n"], 1, "old", "new"))
# lines keep their line breaks: a missing newline at the end, or \r\n for \n, is a difference
print(linediff.unified(["a\n", "b"], ["a\n", "b\n"], 3, "old", "new"), linediff.unified(["a\n", "b"], ["a\n", "b"], 3, "old", "new"))
print(linediff.unified(["a\r\n", "b\r\n", "c"], ["a\n", "b\r\n", "c"], 0, "old", "new"))
# word diffs keep the new text's lines: a line split, a paragraph reflowed, a word removed at a
# line's start, an empty line
print(linediff.worddiff(["a b\n"], ["a\n", "b\n"]), linediff.worddiff(["x\n", "a b\n"], ["x\n", "a\n", "\n", "c b\n"]))
print(linediff.worddiff(["the quick brown fox jumps over\n", "the lazy dog\n"], ["the quick brown\n", "fox leaps over the\n", "lazy dog\n"]))
print(linediff.worddiff(["one two\n", "three\n"], ["two\n", "three four\n"]), linediff.worddiff(["a\n", "b\n"], ["a\n"]), linediff.worddiff(["a\n"], ["a\n", "new line\n"]))

old_text, new_text = gentext.versions(400)
old = [line + "\n" for line in old_text]
new = [line + "\n" for line in new_text]
d = tempfile.mkdtemp()
paths = [os.path.join(d, "old.txt"), os.path.join(d, "new.txt")]
for path, lines in [(paths[0], old), (paths[1], new)]:
    with open(path, "w") as f:
        for line in lines:
            f.write(line)
for n in [3, 1, 0]:
    for line in linediff.unified(old, new, n, "old.txt", "new.txt"):
        print(line)
print(linediff.summary(old, new, False))
for argv in [["--words"], ["-q"], ["--words", "-q"], ["-U", "2", "-q"]]:
    print(argv, "->", linediff.main(argv + paths))
print(linediff.main(["-q", paths[0], paths[0]]))
print(linediff.main(["-x"] + paths), linediff.main([paths[0]]))
ends = [os.path.join(d, "lf.txt"), os.path.join(d, "nolf.txt"), os.path.join(d, "crlf.txt")]
for path, data in [(ends[0], "a\nb\n"), (ends[1], "a\nb"), (ends[2], "a\r\nb\r\n")]:
    with open(path, "w") as f:
        f.write(data)
for argv in [["-q", ends[0], ends[1]], ["-q", ends[1], ends[0]], ["-q", ends[0], ends[2]], ["--words", ends[0], ends[1]], ["-q", ends[1], ends[1]]]:
    print([a.replace(d + "/", "") for a in argv], "->", linediff.main(argv))
for path in paths + ends:
    os.remove(path)
os.rmdir(d)
