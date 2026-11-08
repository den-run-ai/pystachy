with open("/proc/self/status") as f:
    status = f.read()
ign = 0
cgt = 0
for line in status.splitlines():
    if line.startswith("SigIgn:"):
        ign = int(line.split()[1], 16)
    if line.startswith("SigCgt:"):
        cgt = int(line.split()[1], 16)
if ign & 2:
    print("SIGINT ignored")
elif cgt & 2:
    print("SIGINT caught")
else:
    print("SIGINT default")
