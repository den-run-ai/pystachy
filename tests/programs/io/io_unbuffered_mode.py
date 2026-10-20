# open(..., buffering=0): the mode is checked before the buffering
print("before")
f = open("io_unbuffered_mode.txt", "+", 0)
print("not reached")
