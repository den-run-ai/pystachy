# tomllib.loads(): CPython's parser (lib/tomllib), whose documents hold dynamic values, used by a
# program that does not opt in to dynamic Any: every kind of TOML value, tables, arrays of tables,
# dotted and quoted keys, and typed code reading them through isinstance() and annotations
import tomllib
from datetime import date, datetime, time, timedelta
from typing import Any

DOC = r'''
# a project
title = "TOML \"Example\"\t\u00e9\U0001F600"
literal = 'C:\Users\nodejs'
multi = """
Roses are red
  Violets are blue\
   still"""
int = +99
neg = -17
hex = 0xDEAD_beef
oct = 0o755
bin = 0b1101
big = 1_000_000
float = 6.626e-34
exp = 5e+22
frac = -0.01
inf = inf
ninf = -inf
nan = nan
yes = true
no = false
odt = 1979-05-27T07:32:00Z
odt_ms = 1979-05-27T00:32:00.999999-07:00
ldt = 1979-05-27T07:32:00
ld = 1979-05-27
lt = 07:32:00.5
mixed = [1, "two", 3.5, [true], {x = 1}, 1979-05-27]
nested = [[1, 2], ["a", "b"]]
inline = { name = "Tom", "quoted key" = 1, point.x = 1, point.y = 2 }
"key with spaces" = 'spaced'
site."google.com" = true

[owner]
name = "Tom Preston-Werner"
dob = 1979-05-27T07:32:00-08:00

[database]
enabled = true
ports = [ 8000, 8001, 8002 ]
data = [ ["delta", "phi"], [3.14] ]
temp_targets = { cpu = 79.5, case = 72.0 }

[servers.alpha]
ip = "10.0.0.1"
role = "frontend"

[servers.beta]
ip = "10.0.0.2"
role = "backend"

[[products]]
name = "Hammer"
sku = 738594937

[[products]]

[[products]]
name = "Nail"
sku = 284758393
color = "gray"

[[fruits]]
name = "apple"
[fruits.physical]
color = "red"
[[fruits.varieties]]
name = "red delicious"
[[fruits.varieties]]
name = "granny smith"
'''

doc = tomllib.loads(DOC)
for k in doc:
    v = doc[k]
    print(k, type(v).__name__, repr(v))


def typed(doc: dict[str, Any]) -> None:
    # (a program's own types for what it reads: isinstance() narrows, an annotation checks)
    title = doc["title"]
    if isinstance(title, str):
        print(len(title), title.split('"')[1].upper(), title[-1] == "\U0001F600")
    port_sum = 0
    for p in doc["database"]["ports"]:
        if isinstance(p, int):
            port_sum += p
    print(port_sum)
    name: str = doc["owner"]["name"]
    print(name.split()[0])
    dob = doc["owner"]["dob"]
    if isinstance(dob, datetime):
        print(dob.isoformat(), dob.utcoffset(), dob.year)
    ld = doc["ld"]
    if isinstance(ld, date):
        print(ld + timedelta(days=5), ld.weekday())
    lt = doc["lt"]
    if isinstance(lt, time):
        print(lt.hour, lt.minute, lt.microsecond)
    roles = [doc["servers"][s]["role"] for s in doc["servers"]]
    print(roles)
    skus = [p.get("sku", 0) for p in doc["products"]]
    print(skus, sum([s for s in skus if isinstance(s, int)]))


typed(doc)
print(doc["odt"] < doc["owner"]["dob"], doc["odt"] == datetime(1979, 5, 27, 7, 32, tzinfo=doc["odt"].tzinfo))
print(doc["fruits"][0]["varieties"][1]["name"], doc["inline"]["point"], doc["site"])
print(doc["nan"] != doc["nan"], doc["inf"] > 1e308, doc["hex"] + doc["oct"] + doc["bin"])

# a document is a plain dict, which the program may change; CRLF line endings parse too
doc["title"] = "changed"
del doc["mixed"]
doc["database"]["ports"].append(9000)
print(doc["title"], "mixed" in doc, doc["database"]["ports"])
print(tomllib.loads("a = 1\r\nb = 'two'\r\n[t]\r\nc = [3]\r\n"))
print(tomllib.loads(""), tomllib.loads("# only a comment\n"))
print(tomllib.loads("lines = '''\nfirst\n  second'''\nraw = '''a \\ b'''"))
