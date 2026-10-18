# Unicode clauses formerly embedded in mixed stdlib-deviation tests. Keep the
# restored behavior under the ordinary CPython differential oracle.
from datetime import datetime
from random import Random
from statistics import multimode
from string import Template
from urllib.parse import quote

print(repr(datetime.fromisoformat("2024-02-29é12:00")))
print(repr(datetime.fromisoformat("2024-02-29🚀12:00")))
print(len(multimode("ééa")), multimode("ééa") == ["é"])
try:
    Random(3).sample("ñu", 3)
except ValueError as e:
    print("ValueError:", e)
else:
    assert False, "sample population must count code points"
for t in ["é $", "naïve\nnaïve $1"]:
    try:
        Template(t).substitute()
    except ValueError as e:
        print(e)
    else:
        assert False, "invalid placeholder must raise ValueError"
print(quote(chr(233)), quote(chr(195) + chr(169)))
