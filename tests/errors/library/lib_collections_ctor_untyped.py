# error: deque() does not bind its type variable '_T': no argument's type gives it; name it where the object goes
# An empty queue still needs an item type from context or an explicit constructor.
from collections import deque
print(deque())
