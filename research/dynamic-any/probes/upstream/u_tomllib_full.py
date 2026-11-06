# pystachy: dynamic-any
# tomllib on the TOML features: datetimes, special floats, integer bases, strings, tables
import tomllib

with open("full.toml") as f:
    doc = tomllib.loads(f.read())
for k, v in doc.items():
    print(k, "=", repr(v))
