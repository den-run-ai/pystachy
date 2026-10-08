print("rel loaded")
try:
    from .fast import y
except ImportError:
    y = "slow"
