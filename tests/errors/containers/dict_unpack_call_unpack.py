# error: ** of a dict[str,str] is not supported: of a function's **kwargs, or a dict display with str keys, it is
# A dict display with ** makes a dict, whose keys only run time knows, so ** cannot pass them
print("x", "y", **{**{"sep": "-"}})
