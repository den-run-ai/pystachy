"""gencmds: a synthetic shell history for cmdstat.py, the same on every run.

usage: python3 gencmds.py N > HISTORY
Each of the N lines is a command line as a shell's history holds it: commands with options and
arguments, some of them quoted or escaped (spaces, quotes, $, globs), joined into pipelines and
lists by |, &&, || and ;, with redirections; every 500th line has an unclosed quote.
"""
import sys

COMMANDS = ["git", "ls", "cd", "grep", "find", "cat", "echo", "python3", "make", "docker", "ssh",
            "tar", "sed", "xargs", "wc", "sort", "head", "tail", "cp", "mv", "rm", "mkdir", "curl",
            "pystachy"]
OPTIONS = {
    "git": ["status", "log", "--oneline", "-n", "commit", "-m", "diff", "--stat", "checkout", "-b", "push", "-u"],
    "ls": ["-l", "-a", "-la", "-h", "-t", "-R"],
    "grep": ["-r", "-n", "-i", "-v", "-E", "-c", "--color=auto", "-l"],
    "find": ["-name", "-type", "-maxdepth", "-print0", "-mtime"],
    "python3": ["-m", "-c", "-I", "-X", "-u"],
    "make": ["-j8", "-C", "-n", "--keep-going"],
    "docker": ["run", "--rm", "-it", "-v", "build", "-t", "ps", "-a"],
    "tar": ["-xzf", "-czf", "-tvf", "-C"],
    "sed": ["-n", "-i", "-e", "-E"],
    "curl": ["-s", "-L", "-o", "-H", "--fail", "-X"],
    "sort": ["-n", "-r", "-u", "-k2"],
    "head": ["-n", "-20"],
    "tail": ["-f", "-n", "-100"],
    "rm": ["-r", "-f", "-rf", "-i"],
    "cp": ["-r", "-a", "-v"],
    "wc": ["-l", "-w", "-c"],
    "xargs": ["-0", "-n1", "-P4"],
}
WORDS = ["src/main.py", "notes.txt", "~/projects", "README.md", "build/", "tests", "/var/log/syslog",
         "origin", "main", "data.csv", "out.txt", "Makefile", "*.py", "config.yaml", "$HOME", "-", "."]
QUOTED = ["'My Documents'", '"it\'s here"', "'*.py'", '"$HOME/.config"', "'a b c'", '"say \\"hi\\""',
          "'fix: handle '\\''quotes'\\'' in names'", '"tab\\there"', "My\\ File.txt", "\\*.log",
          '"café ☃"', "'2026-10-13 12:00'", '""', "''"]
JOINERS = [" | ", " | ", " && ", " || ", "; "]
REDIRECTS = [" > out.txt", " >> log.txt", " 2>&1", " < input.txt", " 2>/dev/null"]

seed = 20261013


def rand(n: int) -> int:
    # an int in [0, n): a 31-bit linear congruential generator (glibc's constants), whose products
    # stay in 64 bits, as Pystachy's ints do
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed >> 8) % n


def command() -> str:
    # one simple command: a name, options, arguments and maybe a redirection
    name = COMMANDS[rand(len(COMMANDS))]
    parts = [name]
    opts = OPTIONS.get(name, [])
    for _ in range(rand(4) if opts else 0):
        parts.append(opts[rand(len(opts))])
    for _ in range(rand(3)):
        parts.append(QUOTED[rand(len(QUOTED))] if rand(3) == 0 else WORDS[rand(len(WORDS))])
    text = " ".join(parts)
    if rand(6) == 0:
        text += REDIRECTS[rand(len(REDIRECTS))]
    return text


def line(i: int) -> str:
    text = command()
    for _ in range(rand(3) if rand(2) else 0):
        text += JOINERS[rand(len(JOINERS))] + command()
    if i % 500 == 499:
        text += ' "unclosed'
    return text


def main() -> None:
    n = int(sys.argv[1])
    out = sys.stdout
    for i in range(n):
        out.write(line(i) + "\n")


if __name__ == "__main__":
    main()
