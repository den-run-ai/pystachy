# makedirs converts the leaf's mode to C int after making its parents and checking its path.
# Overflow must not create the leaf, even with exist_ok; a newly made parent/. returns early.
import os
import tempfile

tmp = tempfile.mkdtemp()
for mode in [-2147483649, -2147483648, 2147483647, 2147483648, 4294967295]:
    path = os.path.join(tmp, str(mode))
    try:
        os.makedirs(path, mode)
        print(mode, "made")
    except OverflowError as e:
        print(mode, "OverflowError", e)
    print("leaf", os.path.isdir(path))
    if os.path.isdir(path):
        os.rmdir(path)

parent = os.path.join(tmp, "parent")
leaf = os.path.join(parent, "leaf")
try:
    os.makedirs(leaf, 4294967295)
except OverflowError as e:
    print("nested", e)
print("nested paths", os.path.isdir(parent), os.path.isdir(leaf))
if os.path.isdir(leaf):
    os.rmdir(leaf)
try:
    os.makedirs(parent, 4294967295, exist_ok=True)
except OverflowError as e:
    print("existing", e)
os.rmdir(parent)

nul_parent = os.path.join(tmp, "nul-parent")
try:
    os.makedirs(os.path.join(nul_parent, "a\0b"), 4294967295)
except ValueError as e:
    print("nul", e, os.path.isdir(nul_parent))
os.rmdir(nul_parent)

dot_parent = os.path.join(tmp, "dot-parent")
os.makedirs(os.path.join(dot_parent, "."), 4294967295)
print("new dot", os.path.isdir(dot_parent))
try:
    os.makedirs(os.path.join(dot_parent, "."), 4294967295, exist_ok=True)
except OverflowError as e:
    print("existing dot", e)
os.rmdir(dot_parent)
os.rmdir(tmp)
print("removed", not os.path.exists(tmp))
