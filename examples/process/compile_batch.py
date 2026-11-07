"""Compile independent frontend requests with a native pairwise supervisor.

Build with `pystachy build examples/process/compile_batch.py -o compile_batch`.
Run `./compile_batch /absolute/pystachy input1.py input2.py ...`.
A fresh private directory is printed only after every request succeeds. The
compiler children are fresh processes; no semantic state is reused between jobs.
Communication is in input order, with failures handled when their result is read.
"""
import os
import shutil
import sys
import tempfile
from process import Popen


def compile_batch(compiler: list[str], sources: list[str]) -> str:
    directory = tempfile.mkdtemp()
    children: list[Popen] = []
    try:
        # Two at most, including children waiting for their results to be read.
        # The reusable scheduler separately accounts for nested tool threads and memory.
        for start in range(0, len(sources), 2):
            for i in range(start, min(start + 2, len(sources))):
                output = directory + "/" + str(i) + ".ll"
                children.append(Popen(compiler + ["ir", sources[i], "-o", output]))
            for child in children:
                stdout, stderr = child.communicate(timeout=300.0, max_output_bytes=1048576)
                if child.wait() != 0:
                    raise RuntimeError(stderr.decode("utf-8", "replace"))
                if stdout != b"":
                    raise RuntimeError("compiler unexpectedly wrote to stdout")
            for child in children:
                child.close()
            children.clear()
        for i in range(len(sources)):
            if os.path.getsize(directory + "/" + str(i) + ".ll") == 0:
                raise RuntimeError("compiler emitted an empty IR artifact")
    except BaseException:
        for child in children:
            try:
                child.close()
            except TimeoutError:
                pass  # the runtime retains unreaped ownership; close the other children too
        shutil.rmtree(directory)
        raise
    return directory


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise ValueError("usage: compile_batch /absolute/pystachy INPUT.py [INPUT.py ...]")
    print(compile_batch([sys.argv[1]], sys.argv[2:]))
