# pystachy: dynamic-any
# tomllib on a real pyproject.toml, read from a text file
import tomllib

with open("../../../../ports/pyproject.toml") as f:
    doc = tomllib.loads(f.read())
print(doc["project"]["name"], doc["project"]["version"])
print(sorted(doc.keys()))
print(doc)
