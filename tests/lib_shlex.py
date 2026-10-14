# lib/shlex.py: CPython 3.13's shlex with its marked edits (lib/README.md), against CPython's own:
# split() in POSIX and compatibility modes, with and without comments, the shlex class's options
# (whitespace_split, punctuation_chars, commenters, wordchars, quotes, escape), its tokens one by
# one, pushed back and from the sources it pushes and reads, its line numbers and errors, quote()
# and join(). Cases after CPython's Lib/test/test_shlex.py.
import os
import shlex
import tempfile
from io import StringIO


def tokens(lex: shlex.shlex) -> list[str]:
    # the tokens of a lexer, as get_token() returns them, up to its eof, and its ValueError
    out: list[str] = []
    try:
        while True:
            tok = lex.get_token()
            if tok is None or tok == lex.eof:
                return out
            out.append(tok)
    except ValueError as e:
        out.append("ValueError: " + str(e))
    return out


def lexed(lex: shlex.shlex) -> list[str]:
    # the tokens of a lexer, or its ValueError
    try:
        return list(lex)
    except ValueError as e:
        return ["ValueError: " + str(e)]


cases = ["word", "two words", "  padded   out  ", "tab\tand\nnewline", "back\\slash", "\\ lead",
         "trail\\ ", "mid\\ dle word", 'say "two words"', "say 'two words'", '"a" "b" "c"', "'a' b 'c'",
         'glued"quoted"parts\'and\'more', '""', "''", 'empty "" args \'\' here', '\\"', '"\\""',
         '"esc\\ape"', '"back\\\\slash"', '"quote\\"inside"', "'no\\escape'", "'it'\"'\"'s'",
         "a#comment", "a # comment\nb", "#whole line\nnext", "x=1 y=2", "--opt=val -f file",
         "a;b", "a&&b||c", "a>out 2>&1", ":-) ;-)", "caf\xe9 na\xefve ☃", '"caf\xe9 ☃"',
         "\xe9\\\xe9", "a\\\nb", ""]
for s in cases:
    print(repr(s), shlex.split(s), shlex.split(s, comments=True))
    print("  compat", tokens(shlex.shlex(StringIO(s))), tokens(shlex.shlex(s, posix=True)))
    lex = shlex.shlex(s)
    lex.whitespace_split = True
    print("  split, not POSIX", lexed(lex))
for bad in ['"open', "'open", "end\\", '"end\\']:
    try:
        shlex.split(bad)
    except ValueError as e:
        print(repr(bad), "ValueError:", e)
try:
    shlex.split(None)
except ValueError as e:
    print("ValueError:", e)



# punctuation_chars: True, or the characters themselves
for s in ["a && b || c", "a&&b||c", "a ; b;c", "a > b >> c < d", "(a) && (b)", "echo $(ls)|wc -l",
          "~/a&&b-c --color=auto||d *.py?", "f >\"abc\"", "f >\\\"abc\\\"", "'')abc", "a_b__c"]:
    print(repr(s), lexed(shlex.shlex(s, punctuation_chars=True)), lexed(shlex.shlex(s, punctuation_chars="|")),
          lexed(shlex.shlex(s, posix=True, punctuation_chars=True)), lexed(shlex.shlex(s, posix=True, punctuation_chars=False)))
    lex = shlex.shlex(s, punctuation_chars="&")
    lex.whitespace_split = True
    print("  whitespace_split", lexed(lex))
    under = shlex.shlex(s, punctuation_chars="_")
    print("  _", "_" in under.wordchars, lexed(under), under.punctuation_chars)
for punct in ["", "();<>|&"]:
    print(repr(punct), list(shlex.shlex("a(b)|c", punctuation_chars=punct)))
tt = shlex.shlex("a && b || c", punctuation_chars=True)
types: list[tuple[str, str]] = []
for t in tokens(tt):
    types.append((t, "c" if t[0] in tt.punctuation_chars else "a"))
print(types)
uni = shlex.shlex("ℙƴ☂ℌ\xf8ἤ", punctuation_chars=True)
uni.whitespace_split = True
print(list(uni), list(shlex.shlex("ℙƴ☂ℌ\xf8ἤ", punctuation_chars=True)))
print(list(shlex.shlex("\xe9t\xe9 caf\xe9")), list(shlex.shlex("\xe9t\xe9 caf\xe9", posix=True)))

# the options: commenters, wordchars, whitespace, quotes, escape, escapedquotes
lex = shlex.shlex("a;b c%d 'e f'", posix=True)
lex.commenters = "%"
lex.wordchars += ";"
print(lexed(lex))
lex = shlex.shlex("a|b|c d", posix=True)
lex.whitespace = "|"
lex.whitespace_split = True
print(lexed(lex))
lex = shlex.shlex("|a b| 'c d' x|e f|y <g>", posix=True)
lex.quotes = "|"
print(lexed(lex))
lex = shlex.shlex("a^ b ^^c", posix=True)
lex.escape = "^"
print(lexed(lex))
lex = shlex.shlex("'a\\'b' \"c\\\"d\"", posix=True)
lex.escapedquotes = "'\""
print(lexed(lex))

# get_token(), push_token(), read_token(), the line number and the error leader
lex = shlex.shlex("first second\nthird # note\nfourth")
print(lex.get_token(), lex.lineno, lex.get_token(), lex.lineno)
lex.push_token("pushed")
lex.push_token("last-in")
print(lex.get_token(), lex.get_token(), lex.get_token(), lex.lineno, lex.get_token(), lex.lineno)
print(repr(lex.get_token()), repr(lex.get_token()), lex.lineno, repr(lex.error_leader()), repr(lex.error_leader("other", 7)))
raw = shlex.shlex("raw 'tokens'", posix=True)
print(raw.read_token(), raw.read_token(), raw.read_token(), repr(raw.eof), raw.state)
lex = shlex.shlex("one two")
lex.push_source("pushed source")
print(tokens(lex))
lex = shlex.shlex("one two", posix=True)
lex.push_source(StringIO("from a stream"), "stream")
print(lex.get_token(), lex.infile, tokens(lex), repr(lex.infile))
lex = shlex.shlex("noisy", posix=True)
lex.debug = 1
lex.push_token("pushed")
print(lex.get_token(), lex.get_token(), repr(lex.get_token()))
lex = shlex.shlex("a 'b", posix=True)
lex.debug = 3
try:
    print(lexed(lex))
except ValueError as e:
    print("ValueError:", e)

# files, and the sources a lexer reads where its source keyword says
d = tempfile.mkdtemp()
main = os.path.join(d, "main.txt")
inc = os.path.join(d, "inc.txt")
with open(main, "w") as f:
    f.write("a source inc.txt b\nsource \"inc.txt\" c\n")
with open(inc, "w") as f:
    f.write("x 'y z'\n")
with open(main) as f:
    lex = shlex.shlex(f, main, posix=True)
    lex.source = "source"
    lex.wordchars += "."
    got = tokens(lex)
    print(got, lex.lineno, lex.infile == main, repr(lex.error_leader().replace(d, "D")))
with open(main) as f:
    print(shlex.split(f.read()))
spec = shlex.shlex("", main).sourcehook("inc.txt")
print(spec[0] == inc, spec[1].read())
spec[1].close()
spec = shlex.shlex("").sourcehook('"' + inc + '"')
print(spec[0] == inc)
spec[1].close()
os.remove(main)
os.remove(inc)
os.rmdir(d)

# quote() and join()
for s in ["", "safe-word_1@%+=:,./", "test file name", "it's", "a\"b", "$HOME", "back`tick`", "x\\y",
          "bang!", "caf\xe9", "\xe9\xe0\xdf", "tab\there", "new\nline", "*.py", "~user", "a'b'c"]:
    print(repr(s), shlex.quote(s), shlex.split(shlex.quote(s)))
for parts in [["a ", "b"], ["a", " b"], ["a", " ", "b"], ['"a', 'b"'], ["ls", "-l", "my file", "it's"], []]:
    joined = shlex.join(parts)
    print(parts, joined, shlex.split(joined) == parts)

# Unicode punctuation removes that character, preserving other Latin-1 word characters.
print(tokens(shlex.shlex("élève café", posix=True, punctuation_chars="é")))
print(tokens(shlex.shlex("élève café中", posix=True, punctuation_chars="中")))
