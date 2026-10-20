# A NUL in the mode, the encoding or the newline argument is rejected while open() takes its
# arguments, before anything else is checked
print("before")
f = open("io_missing_dir/x.txt", "w", encoding="utf\x008")
print("not reached")
