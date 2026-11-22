# error: has a method frobnicate()
# No member of the union has the method: an error, as it is of each member's type alone.
import json

print(json.loads("1").frobnicate())
