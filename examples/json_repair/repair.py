"""Native entry point for the adapted json_repair command."""
import sys
from json_repair.__main__ import cli

if __name__ == "__main__":
    sys.exit(cli())
