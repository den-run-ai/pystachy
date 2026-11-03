# os.getcwd(): the current directory, as realpath(".") also gives it here (the tests run from the
# repository's root, whose path has no symbolic link), and what posixpath.abspath() and
# logging.FileHandler's baseFilename start from
import os
import posixpath

cwd = os.getcwd()
print(cwd.startswith("/"), cwd == os.path.realpath("."), posixpath.isabs(cwd))
print(posixpath.abspath(".") == cwd, posixpath.abspath("a/../b") == posixpath.join(cwd, "b"))
print(posixpath.abspath("/x//y/./z"), posixpath.dirname(posixpath.abspath("q/r")) == posixpath.join(cwd, "q"))
