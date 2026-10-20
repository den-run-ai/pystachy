# error: expected str, got bytes
# (CPython raises TypeError: decoder should return a string result, not 'bytes')
import io

io.IncrementalNewlineDecoder(None, True).decode(b"x")
