# error: assigning to sys.warnoptions is not supported; change its value in place
# CPython's += extends the list, then binds sys.warnoptions to it again: the change in place is
# sys.warnoptions.extend(["error"])
import sys

sys.warnoptions += ["error"]
