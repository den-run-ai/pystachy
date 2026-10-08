# open(..., buffering=0) of a text file: CPython opens the file first, so a missing directory
# is FileNotFoundError, not "can't have unbuffered text I/O"
print("before")
f = open("io_unbuffered_missing_dir/x.txt", "w", 0)
print("not reached")
