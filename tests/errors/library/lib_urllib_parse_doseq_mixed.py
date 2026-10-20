# error: cannot iterate over tuple[str,int]: its items have different types
# (urlencode() with doseq loops over each value)
from urllib.parse import urlencode

print(urlencode([("a", ("x", 2))], doseq=True))
