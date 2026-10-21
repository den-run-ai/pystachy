# error: emods/syntax_unused.py:2: error: no binding for nonlocal 'zz' found
# (a deviation: a module that an import statement names is checked even where the import never runs)
import sys

if len(sys.argv) > 5:
    import emods.syntax_unused
print("ran")
