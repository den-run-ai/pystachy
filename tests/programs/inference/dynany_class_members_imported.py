# pystachy: dynamic-any
# Class objects of a module that does not opt in, held as Any values: their static and class
# methods, which no typed call compiles, and the functions those call.
from typing import Any

import dynclassmembers

codecs: dict[str, Any] = {"plain": dynclassmembers.Codec, "loud": dynclassmembers.Loud}
for key in sorted(codecs):
    c = codecs[key]
    print(key, c.name, c.version, c.shout("hi"), c.shout("hi", 2), c.shout(times=3, text="a"), c.describe(), c.helper_chain(4))
    try:
        print(c.whisper("x"))
    except AttributeError as e:
        print("AttributeError:", e)
