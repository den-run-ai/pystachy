# Path.glob() given case_sensitive matches every part of the pattern against the directory's
# entries, its literal parts too (CPython's case_pedantic: the file system's case sensitivity is
# not known), so case_sensitive=False finds README.MD for readme.md; without it a literal part is
# joined to the path as it is
import os
import tempfile
from pathlib import Path

d = Path(tempfile.mkdtemp())
(d / "README.MD").write_text("x")
(d / "Sub").mkdir()
(d / "Sub" / "A.TXT").write_text("y")
print(sorted([p.name for p in d.glob("readme.md", case_sensitive=False)]))
print(sorted([p.name for p in d.glob("sub/a.txt", case_sensitive=False)]))
print(sorted([p.name for p in d.glob("sub/*.txt", case_sensitive=False)]))
print(sorted([p.name for p in d.glob("README.MD", case_sensitive=True)]))
print(sorted([p.name for p in d.glob("readme.md", case_sensitive=True)]))
print(sorted([p.name for p in d.glob("README.MD")]))
print(sorted([p.name for p in d.glob("missing.md", case_sensitive=False)]))
print(sorted([p.name for p in d.rglob("a.txt", case_sensitive=False)]))
os.remove(str(d / "Sub" / "A.TXT"))
os.rmdir(str(d / "Sub"))
os.remove(str(d / "README.MD"))
os.rmdir(str(d))
