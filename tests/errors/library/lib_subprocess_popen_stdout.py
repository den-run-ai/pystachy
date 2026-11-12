# error: 'subprocess.Popen' object has no attribute 'stdout'
# A Popen has no stdin, stdout and stderr files: communicate() writes and reads its pipes.
import subprocess

p = subprocess.Popen(["sh", "-c", "echo x"], stdout=subprocess.PIPE)
for line in p.stdout:
    print(line)
