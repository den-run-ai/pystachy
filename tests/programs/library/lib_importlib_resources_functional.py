# importlib.resources' functions of one resource: read_text(), open_text(), is_resource() and
# path(), and as_file() of a path that files() gives.
from importlib import resources
from importlib.resources import as_file, files, is_resource, open_text, read_text

import respkg
import respkg.sub

print(read_text("respkg", "top.txt"), end="")
print(read_text("respkg", "data", "hello.txt", encoding="utf-8"), end="")
print(read_text("respkg", "data", "utf8.txt", encoding="utf-8"), end="")
print(resources.read_text("respkg.sub", "note.txt"), end="")
try:
    read_text("respkg", "data", "hello.txt")
except TypeError as e:
    print(type(e).__name__, e)
try:
    read_text("respkg", "missing.txt")
except FileNotFoundError as e:
    print(type(e).__name__)

with open_text("respkg", "data", "hello.txt", encoding="utf-8") as f:
    print(f.readline(), end="")
    print(f.read(), end="")
with resources.open_text("respkg", "top.txt") as g:
    print([line for line in g])

print(is_resource("respkg", "top.txt"), is_resource("respkg", "data"), is_resource("respkg", "missing.txt"))
print(is_resource("respkg", "data", "hello.txt"), is_resource("respkg.sub", "note.txt"))

with resources.path("respkg", "top.txt") as p:
    print(type(p).__name__, p.name, p.is_file(), p.read_text(), end="")
with as_file(files("respkg") / "data" / "hello.txt") as q:
    print(q.name, q.parent.name, q.exists())
with as_file(files("respkg").joinpath("data")) as d:
    print(d.is_dir(), sorted([entry.name for entry in d.iterdir()]))

try:
    read_text("nope", "top.txt")
except ModuleNotFoundError as e:
    print(type(e).__name__, e)

# the same resources as bytes
from importlib.resources import open_binary, read_binary

print(read_binary("respkg", "data", "utf8.txt"), resources.read_binary("respkg.sub", "note.txt"))
with open_binary("respkg", "data", "hello.txt") as b:
    print(b.read(5), b.read())
