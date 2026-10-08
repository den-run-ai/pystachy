# Documented deviation: files are UTF-8 or Latin-1 only, so an encoding name that is neither
# raises NotImplementedError when the file opens; CPython raises LookupError for a name it does
# not know, such as "u-t-f-8" (its normalization turns it into "u_t_f_8"), and opens files in
# its other codecs.
for e in ["utf-8", "UTF 8", "u-t-f-8"]:
    f = open("/dev/null", "w", encoding=e)
    f.close()
    print(e, "ok")
