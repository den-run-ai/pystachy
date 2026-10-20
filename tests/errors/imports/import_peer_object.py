# error: class inheritance is not supported (the module may have rebound the name 'object' before this statement); CPython creates class C when module 'emods.peer_object' is imported, and its base 'object' may not be a class
import emods.peer_object as p

print(p.C().v)
