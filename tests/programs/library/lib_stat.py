# CPython's own Lib/stat.py (lib/stat.py, unmodified): constants and the S_IS*() tests
import stat
from stat import S_ISDIR, S_IMODE, S_IFMT

modes = [0o040755, 0o100644, 0o120777, 0o020600, 0o010644, 0o140755, 0o060660, 0o104755, 0o041777]
for m in modes:
    print(m, S_ISDIR(m), stat.S_ISREG(m), stat.S_ISLNK(m), stat.S_ISCHR(m), stat.S_ISFIFO(m), stat.S_ISSOCK(m), stat.S_ISBLK(m), stat.S_ISDOOR(m), stat.S_ISPORT(m), stat.S_ISWHT(m), S_IMODE(m), S_IFMT(m))
    print(bool(m & stat.S_ISUID), bool(m & stat.S_ISVTX), m & stat.S_IRWXU, m & stat.S_IRWXG, m & stat.S_IRWXO)
print(stat.S_IRWXU, stat.UF_HIDDEN, stat.SF_SETTABLE, stat.SF_DATALESS, stat.FILE_ATTRIBUTE_HIDDEN, stat.ST_MTIME, stat.S_IFDOOR)
