# error: files() missing 1 required positional argument: 'anchor'
from importlib.resources import files

print(files().name)
