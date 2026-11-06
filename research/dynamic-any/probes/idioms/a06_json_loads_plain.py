# pystachy: dynamic-any
# #485 08d: json.loads of a document whose type depends on the text, used without narrowing
import json

doc = json.loads('{"a": [1, "two", {"b": null}]}')
print(doc["a"][1], type(doc).__name__)
