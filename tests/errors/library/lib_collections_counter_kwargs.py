# error: Counter.__init__() got an unexpected keyword argument 'a'
# Keyword counts are not taken by the constructor (Counter[str] names the type): Counter({'a': 4})
from collections import Counter

print(Counter(a=4, b=2))
