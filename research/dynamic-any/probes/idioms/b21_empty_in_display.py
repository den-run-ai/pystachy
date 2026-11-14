# pystachy: dynamic-any
# empty list and dict displays inside a mixed document display
doc = {"name": "x", "tags": [], "meta": {}, "n": 1}
doc["tags"].append("t")
print(doc)
