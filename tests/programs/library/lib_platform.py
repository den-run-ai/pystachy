# platform (lib/platform.py): uname() and its fields against the system's uname command, which
# reads the same uname(2), and the Python version. The values differ from one machine to the
# next, so the program prints what they must satisfy.
import os
import platform
import sys
import tempfile


def command(flag: str, directory: str) -> str:
    # what "uname FLAG" prints
    path = directory + "/out"
    assert os.system("uname " + flag + " > " + path) == 0
    with open(path) as f:
        text = f.read()
    return text.rstrip("\n")


d = tempfile.mkdtemp()
u = platform.uname()
print(u.system == command("-s", d), u.node == command("-n", d), u.release == command("-r", d))
print(u.version == command("-v", d), u.machine == command("-m", d))
os.remove(d + "/out")
os.rmdir(d)
print(platform.system() == u.system, platform.node() == u.node, platform.release() == u.release)
print(platform.version() == u.version, platform.machine() == u.machine)
print(u[0] == u.system, u[4] == u.machine, platform.uname() is u)
systems = {"linux": "Linux", "darwin": "Darwin", "freebsd": "FreeBSD"}
print(platform.system() == systems[sys.platform], platform.machine() != "", platform.release() != "")
major, minor, patch = platform.python_version_tuple()
print(major == str(sys.version_info.major), minor == str(sys.version_info.minor), patch == str(sys.version_info.micro))
print(platform.python_version() == major + "." + minor + "." + patch)
print(repr(u).startswith("uname_result(system='" + u.system + "', node='"), repr(u).endswith(", machine='" + u.machine + "')"))
if platform.python_implementation() == "PyPy":
    print("PyPy")
