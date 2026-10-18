# A read through a module's self-import alias before its def rebinds an imported name is not
# caught by the loader's rebinding check. CPython prints "base" then "rebound"; Pystachy raises
# NameError at the first read, as the def has not bound its name yet. The later read agrees.
from devmods import star_rebound_self

print(star_rebound_self.greet())
