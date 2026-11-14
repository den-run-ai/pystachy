# os.dup, os.dup2, os.close and os.chdir: redirect standard output to a file and back.
import os
import sys
import tempfile


def captured(directory: str) -> str:
    path = os.path.join(directory, "out.txt")
    sys.stdout.flush()
    saved = os.dup(1)
    with open(path, "w") as target:
        returned = os.dup2(target.fileno(), 1)
    print("hidden", returned)
    sys.stdout.write("written\n")
    sys.stdout.flush()
    os.dup2(saved, 1)
    os.close(saved)
    with open(path) as source:
        return source.read()


def failures() -> None:
    for attempt in range(4):
        try:
            if attempt == 0:
                os.close(987654)
            elif attempt == 1:
                os.dup(987654)
            elif attempt == 2:
                os.dup2(987654, 987655)
            else:
                os.chdir(os.path.join(tempfile.mkdtemp(), "missing"))
        except FileNotFoundError as error:
            print("FileNotFoundError", str(error).startswith("[Errno 2] No such file or directory: '"))
        except OSError as error:
            print(type(error).__name__, error)


directory = tempfile.mkdtemp()
print(repr(captured(directory)))
print("visible again")
start = os.getcwd()
os.chdir(directory)
print(os.path.realpath(os.getcwd()) == os.path.realpath(directory), os.path.exists("out.txt"))
os.chdir(start)
print(os.getcwd() == start)
copy = os.dup(1)
print(copy > 2)
os.close(copy)
failures()
os.remove(os.path.join(directory, "out.txt"))
os.rmdir(directory)
