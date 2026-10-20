# A character above U+00FF written to a Latin-1 file raises UnicodeEncodeError; when nothing
# catches it, the program ends with its line (status 1) after what it printed (a program
# without try or with: tests/programs/io/io_latin1_unencodable_with.py is one with)
print("before")
f = open("/dev/null", "w", encoding="latin-1")
print(f.write("Grüße\n"))
f.write("Grüße: " + chr(0x0141) + chr(0x00F3) + chr(0x0142) + "\n")
print("not reached")
