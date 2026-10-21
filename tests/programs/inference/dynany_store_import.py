# pystachy: dynamic-any
# A display stored into the item of what an imported function declared -> Any returns holds Any
# values (#777), however the function is imported: by name, under another name, through its
# module, or in a function
from typing import Any
from dynstore_helper import get, cont
from dynstore_helper import get as fetch
import dynstore_helper
import dynstore_helper as h

get()["a"] = {}
get()["a"]["n"] = [1]
fetch()["b"] = []
dynstore_helper.get()["c"] = {"k": [2.5]}
h.get()["d"] = [None]


def inner() -> None:
    from dynstore_helper import get as g
    g()["e"] = {}


inner()
print(cont)
