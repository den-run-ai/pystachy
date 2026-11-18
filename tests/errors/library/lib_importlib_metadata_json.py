# error: 'importlib.metadata.Message' object has no attribute 'json'
from importlib.metadata import metadata

print(metadata("demo-pkg").json)
