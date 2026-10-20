# stdout is /dev/full: print(flush=True) raises; CPython keeps the text it could not write,
# so flushing it at exit fails again, is reported, and the status is 120
print("x", flush=True)
print("not reached")
