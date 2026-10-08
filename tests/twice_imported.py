# One file imported under two names, loader.twice.hello and hello (on the module path that
# tests/twice_imported.path sets), is two modules: each runs the file's code, with its own
# __name__ and globals.
import loader.twice.hello
import hello

loader.twice.hello.COUNT = 10
print(loader.twice.hello.COUNT, hello.COUNT)
print(loader.twice.hello.bump(), loader.twice.hello.bump(), hello.bump())
from hello import COUNT

print(COUNT, hello.__name__, loader.twice.hello.__name__)
