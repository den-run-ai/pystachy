# Documented deviations of lib/shlex (CPython 3.13's shlex with marked edits) from CPython.
import os
import shlex
import tempfile
from io import StringIO

# A lexer reads a StringIO: a file's text is read whole when the lexer is made, where CPython's
# reads the file as it asks for characters. After two tokens, CPython prints 'three\n', what is left
# of the file, and False: its lexer's stream is the file.
d = tempfile.mkdtemp()
path = os.path.join(d, "words.txt")
with open(path, "w") as f:
    f.write("one two\nthree\n")
with open(path) as f:
    lex = shlex.shlex(f, path)
    print(lex.get_token(), lex.get_token(), repr(f.read()), isinstance(lex.instream, StringIO))

# A file that push_source() is given is read whole and closed there, where CPython's
# pop_source() closes it: CPython prints False.
lex = shlex.shlex("first")
f = open(path)
lex.push_source(f, path)
print(f.closed, lex.get_token(), lex.get_token(), lex.get_token(), lex.get_token())
os.remove(path)
os.rmdir(d)

# punctuation_chars is a field, which an assignment changes: CPython's is a read-only property
# (AttributeError).
lex = shlex.shlex("a|b", punctuation_chars="|")
lex.punctuation_chars = ";"
print(lex.punctuation_chars)
