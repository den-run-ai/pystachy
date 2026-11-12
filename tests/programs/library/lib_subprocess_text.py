# subprocess in text mode (text, universal_newlines, encoding or errors): str results and input,
# newlines translated; files as the child's streams; getoutput() and getstatusoutput()
import os
import subprocess
import tempfile

done = subprocess.run(["sh", "-c", "echo out; echo err >&2; exit 3"], capture_output=True, text=True)
print(done.returncode, repr(done.stdout), repr(done.stderr))
print(done)
out = done.stdout
if out is not None:
    print(out.upper().splitlines(), out + "!")
done = subprocess.run(["sh", "-c", "printf 'a\\r\\nb\\rc\\n'"], stdout=subprocess.PIPE, universal_newlines=True)
print(repr(done.stdout), done.stderr)
print(repr(subprocess.run(["sh", "-c", "printf 'a\\r\\nb\\rc\\n'"], stdout=subprocess.PIPE).stdout))
print(repr(subprocess.run(["sh", "-c", "exit 0"], capture_output=True, text=True).stdout))
print(subprocess.run(["sh", "-c", "exit 0"], text=True).stdout)

# input is a str, encoded as the output is decoded
done = subprocess.run(["cat"], input="café €\n", capture_output=True, text=True, encoding="utf-8")
print(repr(done.stdout))
done = subprocess.run(["cat"], input="café\n", stdout=subprocess.PIPE, encoding="latin-1")
print(repr(done.stdout))
print(subprocess.run(["cat"], input="café\n".encode("latin-1"), stdout=subprocess.PIPE).stdout)
print(repr(subprocess.run(["cat"], input="", capture_output=True, text=True).stdout))

# bytes that are not the encoding's
bad = "printf 'ok \\377\\376 end\\n'"
print(subprocess.run(["sh", "-c", bad], capture_output=True).stdout)
try:
    subprocess.run(["sh", "-c", bad], capture_output=True, encoding="utf-8")
except UnicodeDecodeError as e:
    print("UnicodeDecodeError", e)
print(repr(subprocess.run(["sh", "-c", bad], capture_output=True, encoding="utf-8", errors="replace").stdout))
print(repr(subprocess.run(["sh", "-c", bad], capture_output=True, encoding="ascii", errors="ignore").stdout))
print(repr(subprocess.run(["sh", "-c", bad], capture_output=True, encoding="utf-8",
                          errors="backslashreplace").stdout))
print(repr(subprocess.run(["sh", "-c", bad], capture_output=True, encoding="latin-1").stdout))
print(repr(subprocess.run(["sh", "-c", "echo plain"], capture_output=True, errors="strict").stdout))

# check_output() returns the output: bytes, or a str in text mode
print(subprocess.check_output(["sh", "-c", "echo  spaced "]).strip().decode())
print(subprocess.check_output(["sh", "-c", "echo text"], text=True).strip().upper())
print(repr(subprocess.check_output("echo both; echo streams >&2", shell=True, stderr=subprocess.STDOUT,
                                   universal_newlines=True)))
print(subprocess.check_output(["sh", "-c", "cat; echo e >&2"], input=b"given\n", stderr=subprocess.DEVNULL))
print(repr(subprocess.check_output(["sh", "-c", "cat"], input="given\n", encoding="utf-8")))
print(subprocess.check_output(["sh", "-c", "cat; echo end"], input=None))
print(repr(subprocess.check_output(["sh", "-c", "cat; echo end"], input=None, text=True)))

# a Popen's pipes carry bytes; a function's annotation names it, and its result
def start(command: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(["sh", "-c", command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)


def finish(p: subprocess.Popen, sent: bytes) -> subprocess.CompletedProcess[bytes]:
    out, err = p.communicate(sent)
    return subprocess.CompletedProcess(p.args, p.wait(), out, err)


def as_text(done: subprocess.CompletedProcess[bytes]) -> subprocess.CompletedProcess[str]:
    out = done.stdout
    return subprocess.CompletedProcess(done.args, done.returncode, None if out is None else out.decode(), "")


with start("cat; echo e >&2") as p:
    made = finish(p, b"sent\r\n")
    print(made, as_text(made))
children: list[subprocess.Popen] = [start("cat"), start("cat >&2")]
print([child.communicate(b"x") for child in children], [child.returncode for child in children])

# files as the child's streams, and their descriptors
d = tempfile.mkdtemp()
name = os.path.join(d, "out.txt")
with open(name, "w") as f:
    f.write("header\n")
    f.flush()
    subprocess.run(["sh", "-c", "echo to the file; echo and its error >&2"], stdout=f, stderr=subprocess.STDOUT)
    raw = subprocess.run(["sh", "-c", "echo by descriptor"], stdout=f.fileno())
    print(raw.stdout, raw.returncode)
with open(name) as f:
    print(repr(f.read()))
with open(name) as f:
    print(subprocess.run(["sh", "-c", "read a; read b; echo $b"], stdin=f, capture_output=True, text=True).stdout)
with open(name, "w") as f:
    subprocess.call(["sh", "-c", "echo out; echo err >&2"], stdout=subprocess.DEVNULL, stderr=f)
    with subprocess.Popen(["sh", "-c", "echo from Popen"], stdout=f.fileno()) as child:
        pass
with open(name) as f:
    print(repr(f.read()))
# close_fds: the child has the parent's other descriptors only without it
with open(name, "w") as f:
    f.write("inherited\n")
with open(name) as f:
    os.set_inheritable(f.fileno(), True)
    reader = ["cat", "/dev/fd/" + str(f.fileno())]
    kept = subprocess.run(reader, close_fds=False, capture_output=True)
    print(kept.returncode, kept.stdout)
    closed = subprocess.run(reader, capture_output=True)
    print(closed.returncode != 0, closed.stdout)
os.remove(name)
os.rmdir(d)

# the shell's output and status
print(subprocess.getstatusoutput("echo out; echo err >&2; exit 3"))
print(subprocess.getstatusoutput("printf 'no newline'"), subprocess.getstatusoutput("echo; echo"))
print(repr(subprocess.getoutput("echo  a   b ; echo c")), repr(subprocess.getoutput("exit 1")))
print(subprocess.getstatusoutput("kill -15 $$"))
print(subprocess.getstatusoutput("printf 'caf\\351\\n'", encoding="latin-1"))
print(subprocess.getoutput("printf '\\377x\\n'", encoding="utf-8", errors="replace"))

print(subprocess.list2cmdline(["a b", "c", 'd"e', "f\\g", "h\\\\\"i", "", "j\\"]))
print(subprocess.PIPE, subprocess.STDOUT, subprocess.DEVNULL)
