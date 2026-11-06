# pystachy: dynamic-any
# CPython 3.13's tomllib, unchanged but for the opt-in comment, parsing a mixed document
import tomllib

doc = tomllib.loads('''
title = "TOML Example"
n = 42
pi = 3.14
ok = true
tags = ["a", "b"]
mixed = [1, "two", 3.5, [true]]
inline = { x = 1, y = "z" }

[owner]
name = "Tom"

[[products]]
name = "Hammer"
sku = 738594937

[[products]]
name = "Nail"
color = "gray"
''')
print(doc)
print(doc["owner"]["name"], doc["products"][1]["color"], doc["mixed"][1], doc["inline"]["y"])
