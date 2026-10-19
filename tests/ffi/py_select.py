# Native select and embedded CPython select coexist and share native file descriptors.
import select
from pyobj import import_module, of_int, of_list

foreign_select = import_module("select").attr("select")
empty = of_list([])
print(select.select([], [], [], 0))
print(foreign_select.call([empty, empty, empty, of_int(0)]))
file = import_module("tempfile").attr("TemporaryFile").call([])
fd = file.attr("fileno").call([]).to_int()
print(select.select([fd], [fd], [], None) == ([fd], [fd], []))
file.attr("close").call([])
try:
    select.select([fd], [], [], 0)
except OSError as error:
    print(type(error).__name__, str(error))
