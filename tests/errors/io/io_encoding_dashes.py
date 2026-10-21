# error: only UTF-8 and Latin-1 files are supported, not encoding='u-t-f-8'
# CPython normalizes the name to "u_t_f_8", which names no codec
f = open("x.txt", "w", encoding="u-t-f-8")
