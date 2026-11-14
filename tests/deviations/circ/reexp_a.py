# Imports circ.reexp_b, which reads this module's copy of circ.reexp_c's K through this module
# before the from-import below binds it (tests/deviations/circular_reexport_unbound.py)
print("circ.reexp_a: start")
from circ import reexp_b
from circ.reexp_c import K
