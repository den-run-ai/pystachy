"""Writes nNN.py, dNN.py, tNN.py and mNN.py: list, dict, tuple and mixed-list displays nested NN deep,
each with the dynamic-any comment, for #781's measurements (pystachy ir FILE -o /dev/null)."""
import sys

for d in [int(a) for a in sys.argv[1:]] or [12, 14, 16, 18, 20, 22]:
    head = "# pystachy: dynamic-any\nprint("
    open(f"n{d}.py", "w").write(head + "[" * d + "2" + "]" * d + ")\n")
    open(f"d{d}.py", "w").write(head + '{"a": ' * d + "2" + "}" * d + ")\n")
    open(f"t{d}.py", "w").write(head + "(" * d + "2," + ")" * d + ")\n")
    open(f"m{d}.py", "w").write(head + "[1, " * d + "2" + "]" * d + ")\n")
