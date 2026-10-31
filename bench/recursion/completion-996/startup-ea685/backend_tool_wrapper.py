#!/usr/bin/env python3
"""Capture actual LLVM driver calls; optionally profile only the selected tool."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

tool = Path(sys.argv[0]).name
real = str(Path(os.environ["ATTR_REAL_LLVM"]) / tool)
directory = os.environ.get("ATTR_DIRECTORY", "")
if not directory:
    os.execv(real, [real, *sys.argv[1:]])
out = Path(directory)
arguments = sys.argv[1:]
source = next((Path(value) for value in arguments if Path(value).name == "prog.ll" and Path(value).is_file()), None)
if tool == "opt" and source is None:
    os.execv(real, [real, *arguments])
assert tool in ("opt", "lli")
record_path = out / (tool + ".json")
assert not record_path.exists(), "refusing to overwrite a prior tool invocation"
record = {"tool": tool, "arguments": arguments, "cwd": os.getcwd(), "instrumented": os.environ["ATTR_STAGE"] == tool}
if tool == "opt":
    data = source.read_bytes()
    (out / "actual-input.ll").write_bytes(data)
    output = Path(arguments[arguments.index("-o") + 1])
    record.update(input_path=str(source), input_sha256=hashlib.sha256(data).hexdigest(), output_path=str(output))
else:
    for fd in (8, 9):
        pieces, offset = [], 0
        while True:
            chunk = os.pread(fd, 1048576, offset)
            if not chunk:
                break
            pieces.append(chunk)
            offset += len(chunk)
        data = b"".join(pieces)
        target = out / ("runtime-fd8.so" if fd == 8 else "input-fd9.bc")
        target.write_bytes(data)
        info = os.fstat(fd)
        record["fd" + str(fd)] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                                  "path": os.readlink("/proc/self/fd/" + str(fd)), "regular_file": stat.S_ISREG(info.st_mode),
                                  "mode": oct(info.st_mode), "offset_before_exec": os.lseek(fd, 0, os.SEEK_CUR)}
        if fd == 8:
            record["fd8"].update(executable=os.access("/proc/self/fd/8", os.X_OK), elf_magic=data[:4].hex(), elf_type=int.from_bytes(data[16:18], "little"))
    assert "-dlopen=/dev/fd/8" in arguments and "/dev/fd/9" in arguments
    assert record["fd8"]["executable"] and record["fd8"]["elf_magic"] == "7f454c46" and record["fd8"]["elf_type"] == 3
inherited = []
for entry in os.listdir("/proc/self/fd"):
    fd = int(entry)
    try:
        if fd > 2 and os.get_inheritable(fd):
            inherited.append(fd)
    except OSError:
        pass
if tool == "lli":
    assert 8 in inherited and 9 in inherited
record["preserved_inheritable_fds"] = sorted(inherited)
command = [real, *arguments]
if record["instrumented"]:
    command = [os.environ["ATTR_VALGRIND"], "--tool=callgrind", "--error-exitcode=99", "--cache-sim=no", "--branch-sim=no",
               "--callgrind-out-file=" + str(out / (tool + ".callgrind")), "--log-file=" + str(out / (tool + "-valgrind.log")), *command]
record["command"] = command
record_path.write_text(json.dumps(record, indent=2) + "\n")
started = time.monotonic()
process = subprocess.run(command, pass_fds=tuple(inherited))
record.update(returncode=process.returncode, observed_tool_wall_s=time.monotonic() - started)
if tool == "opt" and process.returncode == 0:
    data = output.read_bytes()
    (out / "optimized-output.bc").write_bytes(data)
    record["output_sha256"] = hashlib.sha256(data).hexdigest()
record_path.write_text(json.dumps(record, indent=2) + "\n")
sys.exit(process.returncode)
