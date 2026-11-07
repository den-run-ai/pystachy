"""Runs unchanged under CPython, Pystachy JIT and Pystachy AOT."""
import os
import sys
import time
from process import Popen, run
from compile_batch import compile_batch


def checks(python: str, helper: str) -> None:
    initial_fds = len(os.listdir("/proc/self/fd"))
    code, out, err = run(["/bin/cat"], b"hello\x00world\n", timeout=5.0)
    print("binary", code == 0, out == b"hello\x00world\n", err == b"")
    code, out, err = run([python, helper, "outputs"], timeout=5.0)
    print("exit", code == 7, out == b"out", err == b"err")
    code, out, err = run([python, helper, "arguments", "$(false)", "a; b", "two words"], timeout=5.0)
    print("argv", code == 0, out == b"$(false)|a; b|two words", err == b"")
    with Popen(["/bin/cat"]) as first:
        with Popen(["/bin/cat"]) as second:
            print("concurrent", first.poll() is None, second.returncode is None, first.pid != second.pid)
            out2, err2 = second.communicate(b"second", timeout=5.0)
            out1, err1 = first.communicate(b"first", timeout=5.0)
            print("ordered", out1 == b"first", out2 == b"second", err1 == err2 == b"")
    data = b"a\x00b\n" * 32768
    code, out, err = run([python, helper, "duplex"], data, timeout=5.0, max_output_bytes=524288)
    print("duplex", code == 0, out == b"o" * 131072 + data, err == b"e" * 131072 + data[::-1])
    payload = b'[{"name":"allocating","values":[1,2,3]},{"name":"worker","values":[-1,8]}]'
    code, out, err = run([python, helper, "json"], payload, timeout=5.0)
    print("allocation", code == 0, out == b'[{"name":"ALLOCATING","total":6},{"name":"WORKER","total":7}]', err == b"")
    empty: list[str] = []
    for args in [empty, ["cat"], ["/bin/cat", "a\x00b"], ["/bin/cat"] * 4097]:
        try:
            with Popen(args):
                print("bad argv accepted")
        except ValueError:
            print("bad argv rejected")
    try:
        with Popen(["/definitely-missing-pystachy-process"]):
            print("missing accepted")
    except FileNotFoundError:
        print("missing rejected")
    with Popen(["/bin/cat"]) as child:
        for timeout in [-2.0, float("nan"), float("inf")]:
            try:
                child.wait(timeout)
                print("bad timeout accepted")
            except ValueError:
                print("bad timeout rejected")
        try:
            child.wait(0.0)
            print("wait accepted")
        except TimeoutError:
            print("wait timeout", child.poll() is None)
        child.terminate()
        print("terminate", child.wait(5.0) == -15)
    with Popen(["/bin/sleep", "30"]) as child:
        try:
            child.communicate(timeout=0.0)
            print("timeout accepted")
        except TimeoutError:
            print("communicate timeout", child.wait(5.0) == -9)
    with Popen([python, helper, "flood"]) as child:
        try:
            child.communicate(timeout=5.0, max_output_bytes=1024)
            print("limit accepted")
        except BufferError:
            print("output bounded", child.wait(5.0) == -9)
    with Popen(["/bin/cat"]) as child:
        child.communicate(timeout=5.0, max_output_bytes=0)
        try:
            child.communicate(timeout=5.0)
            print("duplicate accepted")
        except ValueError:
            print("duplicate rejected")
    child = Popen(["/bin/sleep", "30"])
    child.close()
    child.close()
    try:
        child.poll()
        print("closed accepted")
    except ValueError:
        print("closed rejected")
    with Popen(["/bin/cat"]) as child:
        child.kill()
        print("kill", child.wait(5.0) == -9)
    code, out, err = run([python, helper, "closed"], data, timeout=5.0)
    print("closed stdin", code == 0, out == b"", err == b"")
    owned: list[Popen] = []
    try:
        for i in range(64):
            owned.append(Popen(["/bin/cat"]))
        try:
            with Popen(["/bin/cat"]):
                print("count accepted")
        except RuntimeError:
            print("count bounded")
    finally:
        for item in owned:
            item.close()
    code, out, err = run(["/bin/cat"], b"again", timeout=5.0)
    print("reuse", code == 0, out == b"again", err == b"")
    print("descriptor cleanup", len(os.listdir("/proc/self/fd")) == initial_fds)


mode = sys.argv[1]
if mode == "checks":
    checks(sys.argv[2], sys.argv[3])
elif mode == "compile":
    print(compile_batch([sys.argv[2], sys.argv[3]], sys.argv[4:]))
elif mode == "fd-boundary":
    try:
        status, stdout, stderr = run([sys.argv[2], sys.argv[3], "fd-check", sys.argv[4], sys.argv[5]], timeout=5.0)
        print(stdout.decode().strip())
        print(status == 0, stderr == b"")
    except OSError:
        print("rejected before exec")
elif mode == "sigchld":
    try:
        run([sys.argv[2], sys.argv[3], "fd-check", "-1", sys.argv[4]], timeout=5.0)
        print("unexpected child")
    except NotImplementedError as error:
        print("host rejected", "SIGCHLD" in str(error))
elif mode == "descendant":
    status, stdout, stderr = run([sys.argv[2], sys.argv[3], "descendant"], timeout=5.0)
    print(stdout.decode().strip())
    print(status == 0, stderr == b"")
else:
    child = Popen(["/bin/sleep", "30"])
    print(child.pid, flush=True)
    if mode == "wait":
        child.wait()
    elif mode == "sleep":
        time.sleep(30.0)
    elif mode == "error":
        raise ValueError("owner failure")
    # "abandon" returns without an explicit close; native runtime finalization owns it.
