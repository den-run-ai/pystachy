# pystachy: dynamic-any
# tomllib.loads() -> edit -> tomli_w.dumps() -> tomllib.loads(): both libraries upstream, opted in
import tomllib

import tomli_w

with open("full.toml") as f:
    doc = tomllib.loads(f.read())
del doc["nnan"]  # (nan != nan would fail the equality check below)
doc["fruits"].append({"name": "cherry", "count": 3, "weights": [1.5, 2]})
doc["a"]["b"]["c"] += 1
text = tomli_w.dumps(doc)
print(text)
again = tomllib.loads(text)
print(again == doc)
