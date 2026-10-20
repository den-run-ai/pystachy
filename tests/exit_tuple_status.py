# sys.exit((3,)) in a program without try: SystemExit(3), status 3 and nothing on stderr, as for
# sys.exit(3).
import sys

print("bye", flush=True)
sys.exit((3,))
