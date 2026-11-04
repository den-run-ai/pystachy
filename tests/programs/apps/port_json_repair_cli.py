import os
import tempfile
from json_repair.__main__ import cli

directory = tempfile.mkdtemp()
source = os.path.join(directory, "source.json")
target = os.path.join(directory, "target.json")
with open(source, "w", encoding="utf-8") as f:
    f.write('{name: "café", values: [true, null,],}')
print(cli([source, "-o", target, "--ensure_ascii"]))
with open(source, encoding="utf-8") as f:
    print(f.read())
with open(target, encoding="utf-8") as f:
    print(f.read())
print(cli(["--inline", source]))
with open(source, encoding="utf-8") as f:
    print(f.read())
with open(source, "wb") as binary_output:
    binary_output.write(br'{"value":"\ud800"}')
print(cli(["--inline", source]))
with open(source, "rb") as binary_input:
    print(binary_input.read())
os.remove(target)
os.remove(source)
os.rmdir(directory)
