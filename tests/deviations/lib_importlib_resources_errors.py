# importlib.resources.read_text() and open_text() take no error handler but 'strict', as
# Path.open(): Pystachy's files have none. CPython decodes with the handler.
from importlib.resources import read_text

import devres

print(read_text("devres", "note.txt"), end="")
try:
    print(read_text("devres", "note.txt", errors="replace"), end="")
except NotImplementedError as e:
    print(type(e).__name__, e)
