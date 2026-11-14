# subprocess.Popen: poll(), wait(), communicate(), the signals, and timeouts
import os
import subprocess
import time

p = subprocess.Popen(["sh", "-c", "read x; echo got $x; exit 2"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
print(p.args, p.pid > 0, p.returncode, p.poll())
out, err = p.communicate(b"line\n")
print(out, err, p.returncode, p.poll(), p.wait())
print(p.communicate())

# wait() with a timeout; the child goes on
p = subprocess.Popen(["sleep", "30"])
try:
    p.wait(timeout=0.05)
except subprocess.TimeoutExpired as e:
    print("TimeoutExpired", e, e.cmd, e.timeout, e.output, e.stdout, e.stderr)
print(p.poll())
p.terminate()
print(p.wait(), p.returncode, p.poll())
p.terminate()
p.kill()
p.send_signal(9)
print(p.wait(timeout=0))

p = subprocess.Popen("sleep 30", shell=True)
p.kill()
print(p.wait(timeout=10))
p = subprocess.Popen(["sleep", "30"])
p.send_signal(14)
print(p.wait())

# communicate() with a timeout keeps what it has read, for the next call
p = subprocess.Popen(["sh", "-c", "echo first; echo e1 >&2; exec sleep 30"], stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)
try:
    p.communicate(timeout=2)
except subprocess.TimeoutExpired as e:
    print("TimeoutExpired", e, e.output, e.stderr, e.timeout)
p.kill()
print(p.communicate(), p.returncode)

# as a context manager it waits for the child
with subprocess.Popen(["sh", "-c", "exit 6"]) as p:
    pass
print(p.returncode)
with subprocess.Popen(["cat"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
    print(p.communicate(input=b"through cat"))
print(p.returncode)

# run() kills a child that takes longer than timeout
start = time.monotonic()
try:
    subprocess.run(["sh", "-c", "exec sleep 30"], capture_output=True, timeout=0.25)
except subprocess.TimeoutExpired as e:
    print("TimeoutExpired", e, e.output, e.stderr, e.cmd)
print(time.monotonic() - start < 20)
try:
    subprocess.run("exec sleep 30", shell=True, timeout=0.1)
except subprocess.TimeoutExpired as e:
    print("TimeoutExpired", e, e.output, e.timeout)
try:
    subprocess.check_output(["sleep", "30"], timeout=1)
except subprocess.TimeoutExpired as e:
    print("TimeoutExpired", e, e.timeout)
try:
    subprocess.call(["sleep", "30"], timeout=0.1)
except subprocess.TimeoutExpired as e:
    print("TimeoutExpired", e)
try:
    subprocess.run(["sleep", "30"], timeout=-1)
except subprocess.TimeoutExpired as e:
    print("TimeoutExpired", e)

# a new session: the child leads its process group
leader = "kill -s 0 -- -$$ 2>/dev/null && echo leader || echo member"
print(subprocess.run(["sh", "-c", leader], capture_output=True).stdout)
print(subprocess.run(["sh", "-c", leader], capture_output=True, start_new_session=True).stdout)

# many children: none is left, and no descriptor
before = len(os.listdir("/dev/fd"))
for i in range(50):
    done = subprocess.run(["sh", "-c", "echo $0; echo e >&2", str(i)], input=b"in", capture_output=True)
    if done.stdout != str(i).encode() + b"\n" or done.returncode:
        print("unexpected", i, done)
    try:
        subprocess.run(["pystachy-no-such-program"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass
    try:
        subprocess.run(["sleep", "30"], capture_output=True, timeout=0)
    except subprocess.TimeoutExpired:
        pass
print(len(os.listdir("/dev/fd")) == before)
