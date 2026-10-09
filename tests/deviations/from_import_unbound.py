# Documented deviation: from m import x of a global that m's code has not bound yet (here because
# of a circular import) raises ImportError: cannot import name 'x' from 'circ.first' (path), with
# the real path of m's file as compiled, where CPython says: cannot import name 'x' from partially
# initialized module 'circ.first' (most likely due to a circular import) (/path/to/circ/first.py)
try:
    from circ import first

    print(first.f())
except (ImportError, AttributeError) as e:
    print(type(e).__name__, "partially initialized" in str(e), str(e).endswith("circ/first.py)"))
