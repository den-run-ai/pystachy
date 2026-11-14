# subprocess's exceptions: a status that check=True refuses, a program that cannot start
import os
import subprocess

# CalledProcessError: its message, and what it holds
try:
    subprocess.run(["sh", "-c", "echo out; echo err >&2; exit 3"], check=True, capture_output=True)
except subprocess.CalledProcessError as e:
    print("CalledProcessError", e, e.returncode, e.cmd, e.output, e.stdout, e.stderr)
    out = e.stderr
    if out is not None:
        print(out.decode().strip())
try:
    subprocess.run("exit 2", shell=True, check=True)
except subprocess.CalledProcessError as e:
    print("CalledProcessError", e, e.returncode, e.cmd, e.output, e.stdout, e.stderr)
try:
    subprocess.check_call(["sh", "-c", "exit 9"])
except subprocess.SubprocessError as e:
    print(type(e).__name__, e)
try:
    subprocess.check_output(["sh", "-c", "echo partial; echo e >&2; exit 5"], stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as e:
    print("CalledProcessError", e, e.output, e.stderr)
print(subprocess.run(["sh", "-c", "exit 0"], check=True).returncode)

# a child that a signal ended
for command in ("kill -9 $$", "kill -15 $$", "kill -13 $$", "kill -6 $$", "kill -14 $$"):
    try:
        subprocess.run(["sh", "-c", command], check=True)
    except subprocess.CalledProcessError as e:
        print(e.returncode, e)
e = subprocess.CalledProcessError(-63, "x")
print(e)
e = subprocess.CalledProcessError(1, ["a", "b c"], b"o", b"e")
print(e, e.output, e.stdout, e.stderr, isinstance(e, subprocess.SubprocessError), isinstance(e, Exception))
e.stdout = b"changed"
print(e.output)

# CompletedProcess.check_returncode()
done = subprocess.run(["sh", "-c", "echo o; exit 4"], stdout=subprocess.PIPE)
try:
    done.check_returncode()
except subprocess.CalledProcessError as e:
    print("CalledProcessError", e, e.output, e.stderr)
subprocess.run(["sh", "-c", "exit 0"]).check_returncode()
made = subprocess.CompletedProcess(["x", "y"], 1, b"made")
print(made, made.args, made.returncode, made.stdout, made.stderr)
try:
    made.check_returncode()
except subprocess.CalledProcessError as e:
    print("CalledProcessError", e, e.output, e.stderr)
print(subprocess.CompletedProcess("x y", 0))

# TimeoutExpired
t = subprocess.TimeoutExpired(["sleep", "1"], 2.5, b"so far")
print(t, t.cmd, t.timeout, t.output, t.stdout, t.stderr, isinstance(t, subprocess.SubprocessError))
t.stdout = None
print(t.output, subprocess.TimeoutExpired("sleep 1", 3))

# a program that is not there, is no program, or is in no directory
for args in (["pystachy-no-such-program", "x"], ["/nonexistent/dir/program"], ["./"], ["/dev/null"], [""]):
    try:
        subprocess.run(args, capture_output=True)
    except OSError as e:
        print(type(e).__name__, e)
try:
    subprocess.Popen(["sh", "-c", "true"], cwd="/nonexistent/dir")
except FileNotFoundError as e:
    print("FileNotFoundError", e)
try:
    subprocess.run(["sh", "-c", "true"], cwd="/dev/null")
except NotADirectoryError as e:
    print("NotADirectoryError", e)
try:
    subprocess.check_output("pystachy-no-such-program")
except FileNotFoundError as e:
    print("FileNotFoundError", e)
# the shell is there: its status says that its command is not
print(subprocess.run("pystachy-no-such-program", shell=True, stderr=subprocess.DEVNULL).returncode)
try:
    subprocess.run([])
except IndexError as e:
    print("IndexError", e)

# arguments that CPython refuses
try:
    subprocess.run(["sh", "-c", "true"], input=b"x", stdin=subprocess.PIPE)
except ValueError as e:
    print("ValueError", e)
try:
    subprocess.run(["sh", "-c", "true"], capture_output=True, stderr=subprocess.PIPE)
except ValueError as e:
    print("ValueError", e)
try:
    subprocess.run(["sh", "-c", "true"], env={"A=B": "c"})
except ValueError as e:
    print("ValueError", e)
try:
    subprocess.run(["sh", "-c\0", "true"])
except ValueError as e:
    print("ValueError", e)
try:
    subprocess.run(["sh", "-c", "true"], env={"A": "b\0c"})
except ValueError as e:
    print("ValueError", e)
try:
    subprocess.run(["sh", "-c", "true"], text=True, universal_newlines=False)
except subprocess.SubprocessError as e:
    print("SubprocessError", e)
p = subprocess.Popen(["sh", "-c", "cat"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
print(p.communicate(b"once"))
try:
    p.communicate(b"twice")
except ValueError as e:
    print("ValueError", e)
print(p.communicate())

# a descriptor that is not open, or is none
for fd in (987654, -5, 2**31, -2**31 - 1):
    try:
        subprocess.run(["sh", "-c", "true"], stdout=fd)
    except (OSError, OverflowError) as e:
        print(type(e).__name__, e)
try:
    subprocess.run(["sh", "-c", "true"], stdin=subprocess.STDOUT)
except OSError as e:
    print(type(e).__name__, e)
try:
    subprocess.run(["sh", "-c", "true"], stdout=subprocess.STDOUT)
except ValueError as e:
    print("ValueError", e)
print(subprocess.run(["sh", "-c", "echo e >&2"], stderr=-3, stdout=subprocess.DEVNULL).stderr)
print(os.getcwd() != "")
