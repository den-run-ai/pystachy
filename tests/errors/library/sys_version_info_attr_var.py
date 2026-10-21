# error: type tuple[int,int,int,str,int] has no attribute 'major'
# sys.version_info's value is a tuple of its items: its attributes are read as
# sys.version_info.major and the like, not through a variable
import sys

v = sys.version_info
print(v.major)
