# Dates are dict keys (#484 hashes objects by their class's __hash__ and __eq__; #482's date
# hashes its fields, as upstream's _getstate() bytes, which Pystachy does not have).
from datetime import date

counts = {date(2024, 2, 29): 1}
print(counts)
