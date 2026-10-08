# open(..., buffering=0) checks the opened file before the buffering: a directory is
# IsADirectoryError
print("before")
f = open(".", "r", buffering=0)
print("not reached")
