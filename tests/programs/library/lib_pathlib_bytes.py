# Path.read_bytes() and Path.write_bytes(): the file's bytes as they are, with no decoding and no
# newline translation; write_bytes() replaces the file and returns the count; a missing parent
# and a directory raise open()'s errors
import tempfile
from pathlib import Path


def main() -> None:
    base = Path(tempfile.mkdtemp())
    p = base / "data.bin"
    print(p.write_bytes(b"\xef\xbb\xbfname = 1\r\n\x00\xff"))
    data = p.read_bytes()
    print(len(data), data[:3] == b"\xef\xbb\xbf", data[-4:], type(data).__name__)
    print(p.write_bytes(b"ab"), p.read_bytes(), p.read_text())
    print(p.write_bytes(b""), p.read_bytes() == b"", p.read_text() == "", p.exists())
    p.write_text("café\n")
    print(p.read_bytes(), len(p.read_bytes()))
    copy = base / "copy.bin"
    print(copy.write_bytes(p.read_bytes()), copy.read_text() == p.read_text())
    q = base / "missing" / "x.bin"
    for attempt in ("read", "write"):
        try:
            if attempt == "read":
                q.read_bytes()
            else:
                q.write_bytes(b"x")
        except FileNotFoundError as error:
            print(attempt, type(error).__name__)
    try:
        base.read_bytes()
    except IsADirectoryError as error:
        print(type(error).__name__)
    p.unlink()
    copy.unlink()
    base.rmdir()
    print(base.exists())


main()
