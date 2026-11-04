# error: _static_argparse_schema_required
import argparse

factory = argparse.ArgumentParser
parser = factory()
parser.parse_args([])
