# error: module 'inspect' has no attribute 'getmembers'
# what asks a live object for its members, source or frames is not provided
import inspect

print(inspect.getmembers(3))
