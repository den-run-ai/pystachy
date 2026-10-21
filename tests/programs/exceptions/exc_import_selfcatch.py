# An optional import of a module whose code raises ImportError and catches it itself: the import
# succeeds.
try:
    import mods.selfcatch
except ImportError:
    print("fallback")
else:
    print("imported", mods.selfcatch.VALUE)
