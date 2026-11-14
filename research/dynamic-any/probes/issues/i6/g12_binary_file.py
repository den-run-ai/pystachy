with open("/etc/hostname", "rb") as f:
    print(len(f.read()) > 0)
