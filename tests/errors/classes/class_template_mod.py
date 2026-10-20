# error: class emods.ctnever.Never is not supported: cannot infer the type of field 'v'; annotate it (self.v: T = ...) (specializing emods.ctnever.Never(int) for the call at tests/errors/classes/class_template_mod.py:5)
from emods.ctnever import Fine, Never

print(Fine(1).v)
print(Never(1).v)
