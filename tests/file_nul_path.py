import os
print(os.path.exists("/dev/null\x00x"), os.getenv("PATH\x00", "dflt"))
os.remove("/nonexistent\x00b")
