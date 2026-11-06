# pystachy: dynamic-any
import jmespath
doc = {"a": {"b": [1, "two", {"c": 3.5}]}, "people": [{"name": "a", "age": 30}, {"name": "b", "age": 20}]}
print(jmespath.search("a.b[2].c", doc))
print(jmespath.search("people[?age > `25`].name", doc))
