# error: expected CompletedProcess[str], got CompletedProcess[bytes]
# run() in text mode returns a CompletedProcess[str], and otherwise a CompletedProcess[bytes]: a
# variable holds one of the two, as it holds values of one type.
import subprocess

done = subprocess.run(["sh", "-c", "echo x"], capture_output=True, text=True)
print(done.stdout)
done = subprocess.run(["sh", "-c", "echo x"], capture_output=True)
print(done.stdout)
