# error: argparse schema: parser cannot escape or be rebound
import argparse

p = argparse.ArgumentParser(prog="tool")
alias = p
alias.add_argument("filename")
