# A character above U+00FF written to a Latin-1 file raises UnicodeEncodeError; when nothing
# catches it, the program ends with its line (status 1) after what it printed (here through the
# with statement, which closes the file)
print("before")
with open("/dev/null", "w", encoding="latin-1") as f:
    print(f.write("Grüße\n"))
    f.write("5 €€\n")
print("not reached")
