# pystachy: dynamic-any
# an empty list display nested two levels down in a list of mixed records
data = [
    {"a": 1, "user": {"role": "admin", "flags": ["beta"]}},
    {"a": 1.5, "user": {"role": "dev", "flags": []}},
]
print(data)
