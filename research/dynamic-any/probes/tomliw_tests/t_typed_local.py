# pystachy: dynamic-any
# a document built in an annotated dict[str, str] local, passed to an Any API
import tomli_w

doc: dict[str, str] = {}
doc["a"] = "x"
print(tomli_w.dumps(doc))
