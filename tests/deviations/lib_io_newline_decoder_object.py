# IncrementalNewlineDecoder's decoder: CPython's calls its decode() first, for bytes; Pystachy's
# takes only decoder=None, with str input, and raises NotImplementedError for another
import io


class Latin1:
    def decode(self, data: bytes, final: bool = False) -> str:
        return data.decode("latin-1")


try:
    io.IncrementalNewlineDecoder(Latin1(), True)
    print("made")
except NotImplementedError as e:
    print("NotImplementedError:", e)
