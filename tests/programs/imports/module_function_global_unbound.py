# A module global that only a function of its module assigns, read before the function runs:
# AttributeError, as in CPython.
import infer.conf as conf

print("before")
print(conf.late)
