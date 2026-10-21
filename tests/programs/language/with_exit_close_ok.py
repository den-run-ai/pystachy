# Detection reaches a with inside a method; a successful close preserves SystemExit's status.
import sys


class Writer:
    def stop(self) -> None:
        with open("/dev/null", "w") as f:
            f.write("kept")
            sys.exit(7)


Writer().stop()
