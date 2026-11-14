# error: expected list[str] | str, got tuple[str,str,str]
# args is a str or a list of str. CPython also takes other sequences, and bytes and paths.
import subprocess

print(subprocess.run(("sh", "-c", "exit 0")).returncode)
