# open(..., buffering=0) of a file that opens: "can't have unbuffered text I/O" comes before
# the text layer checks its newline and encoding arguments
print("before")
f = open("/dev/null", "w", 0, newline="zz")
print("not reached")
