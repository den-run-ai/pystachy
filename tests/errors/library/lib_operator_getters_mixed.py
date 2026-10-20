# error: lib_operator_getters_mixed.py:5: error: expected itemgetter(0), got itemgetter(1)
# Each literal item makes an itemgetter of its own, as a class template's specializations
from operator import itemgetter

getters = [itemgetter(0), itemgetter(1)]
print([g((5, 6)) for g in getters])
