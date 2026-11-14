# pystachy: dynamic-any
# string.Template.substitute with a dict of Any values
from string import Template
from typing import Any

d: dict[str, Any] = {"who": "world", "n": 3}
print(Template("hello $who x$n").substitute(d))
