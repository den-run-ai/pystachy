# importlib.resources.files() of a namespace package (a directory without __init__.py) is not
# supported: CPython gives a MultiplexedPath of the package's directories.
from importlib.resources import files

import devmods.resource_part

print(devmods.resource_part.PART)
try:
    print(files("devmods").joinpath("resource_part.py").is_file())
except NotImplementedError as e:
    print(type(e).__name__, e)
print(files("devmods.resource_part").name)
