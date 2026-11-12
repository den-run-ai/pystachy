# error: module 'colorsys' cannot be used as a value
import colorsys
from importlib.resources import files

print(files(colorsys).name)
