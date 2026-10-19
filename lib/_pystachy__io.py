"""The io module provides the Python interfaces to stream handling. The
builtin open function is defined in this module.

At the top of the I/O hierarchy is the abstract base class IOBase. It
defines the basic interface to a stream. Note, however, that there is no
separation between reading and writing to streams; implementations are
allowed to raise an OSError if they do not support a given operation.

Extending IOBase is RawIOBase which deals simply with the reading and
writing of raw bytes to a stream. FileIO subclasses RawIOBase to provide
an interface to OS files.

BufferedIOBase deals with buffering on a raw byte stream (RawIOBase). Its
subclasses, BufferedWriter, BufferedReader, and BufferedRWPair buffer
streams that are readable, writable, and both respectively.
BufferedRandom provides a buffered interface to random access
streams. BytesIO is a simple stream of in-memory bytes.

Another IOBase subclass, TextIOBase, deals with the encoding and decoding
of streams into text. TextIOWrapper, which extends it, is a buffered text
interface to a buffered raw stream (`BufferedIOBase`). Finally, StringIO
is an in-memory stream for text.

Argument names are not part of the specification, and only the arguments
of open() are intended to be used as keyword arguments.

data:

DEFAULT_BUFFER_SIZE

   An int containing the default buffer size used by the module's buffered
   I/O classes. open() uses the file's blksize (as obtained by os.stat) if
   possible.
"""
# _io for Pystachy: CPython builds _io into its interpreter (Modules/_io), and its io module is a
# Python layer over it. Pystachy's io (lib/io.py) is the implementation itself, so this file, which
# Pystachy loads for import _io (specs.STANDINS), gives io's classes and functions under _io's
# names. Not here: FileIO, the Buffered* classes and open_code(), which need binary files that
# open() does not make (#493); the _IOBase, _RawIOBase, _BufferedIOBase and _TextIOBase base
# classes, which io's classes do not derive from; and UnsupportedOperation, which, as io's, a
# program cannot name (lib/compatibility.md). The docstring is CPython 3.13.16's.
from io import (DEFAULT_BUFFER_SIZE, BlockingIOError, open, text_encoding, StringIO, BytesIO, TextIOWrapper,
                IncrementalNewlineDecoder)
