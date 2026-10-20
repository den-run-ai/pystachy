# A module whose code raises the first time it runs, and ends the next (tests/programs/imports/import_try_binding.py)
import runs

N = runs.incr()
print("flaky: run", N)
if N == 1:
    raise ValueError("flaky raises on its first run")
X = 10
