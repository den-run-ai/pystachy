# error: 'emods.readcyc_a.A' is a variable, so it cannot be called
# (an alias through a module's attribute stays an error where a statement before it imports a
# module whose code imports the alias's module back: readcyc_b's code reads readcyc_a.A before
# readcyc_a's alias statement runs, where CPython raises AttributeError)
import emods.readcyc_a

print("main")
