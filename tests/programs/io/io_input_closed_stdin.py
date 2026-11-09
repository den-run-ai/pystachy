# stdin is closed when the program starts (tests/run.sh closes it for a program named *_closed_stdin),
# so CPython's sys.stdin is None for the whole run: input() raises RuntimeError before it writes a
# prompt or converts one that is not a str, even once open() has given a file descriptor 0
import os
import tempfile


class Prompt:
    def __str__(self) -> str:
        print("str() of the prompt")
        return "prompt> "


try:
    print("got", repr(input()))
except (RuntimeError, EOFError) as e:
    print("input()", type(e).__name__, e)
try:
    print("got", repr(input("prompt> ")))
except (RuntimeError, EOFError) as e:
    print("input(str)", type(e).__name__, e)
try:
    print("got", repr(input(Prompt())))
except (RuntimeError, EOFError) as e:
    print("input(Prompt())", type(e).__name__, e)
directory = tempfile.mkdtemp()
path = os.path.join(directory, "lines")
with open(path, "w") as writer:
    writer.write("a line of the file\n")
with open(path) as reader:
    print("the file is descriptor 0:", reader.fileno() == 0)
    try:
        print("got", repr(input()))
    except (RuntimeError, EOFError) as e:
        print("input() after open()", type(e).__name__, e)
    print("the file reads", repr(reader.readline()))
os.remove(path)
os.rmdir(directory)
input()
print("not reached")
