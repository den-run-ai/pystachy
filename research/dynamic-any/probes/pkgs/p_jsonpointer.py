# pystachy: dynamic-any
from jsonpointer import resolve_pointer
doc = {"a": [{"b": 1}, {"b": "two"}], "c": {"d e": None}}
print(resolve_pointer(doc, "/a/1/b"), resolve_pointer(doc, "/c/d e"), resolve_pointer(doc, "/x", "dflt"))
