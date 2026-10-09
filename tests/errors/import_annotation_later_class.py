# error: emods/later.py:6: error: name 'Derived' is not defined
# The program's from __future__ import annotations does not reach the modules it imports: their
# defs evaluate their annotations, and a class defined further on (a subclass, here) is not bound.
from __future__ import annotations

import emods.later

print(emods.later.g())
