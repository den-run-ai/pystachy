# error: class emods.singleton_body.Sentinel is not supported: its body holds statements other than fields, methods and a docstring
# (the class of a class rebound to its instance keeps its name in messages: class_singleton)
from emods.singleton_body import Sentinel

print(Sentinel)
