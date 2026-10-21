# A zero step raises before consuming any iterable, including files or invalid inputs.
import os
import tempfile
from typing import Iterator

folder = tempfile.mkdtemp()
path = os.path.join(folder, 'slice.txt')
with open(path, 'w') as writer:
    writer.write('one\ntwo\n')

xs: list[str] = []
with open(path) as source:
    try:
        xs[::0] = source
    except ValueError as e:
        print(e)
    print(repr(source.readline()))  # the first line proves the position was unchanged
    xs[:] = source
    print(xs, repr(source.read()))

with open(path) as closed:
    closed.close()
    try:
        xs[::0] = closed
    except ValueError as e:
        print(e)

absent: list[str] | None = None
try:
    xs[::0] = absent
except ValueError as e:
    print(e)

class Broken:
    def __iter__(self) -> Iterator[str]:
        print('iter must not run')
        raise RuntimeError('unexpected iteration')
        return iter(['never'])

try:
    xs[::0] = Broken()
except ValueError as e:
    print(e)

os.remove(path)
os.rmdir(folder)
