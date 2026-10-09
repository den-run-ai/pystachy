# error: syntax_blocks_with_items.py:25: error: too many statically nested blocks
# each item of a with statement is a block
with (
    open("/dev/null") as f0,
    open("/dev/null") as f1,
    open("/dev/null") as f2,
    open("/dev/null") as f3,
    open("/dev/null") as f4,
    open("/dev/null") as f5,
    open("/dev/null") as f6,
    open("/dev/null") as f7,
    open("/dev/null") as f8,
    open("/dev/null") as f9,
    open("/dev/null") as f10,
    open("/dev/null") as f11,
    open("/dev/null") as f12,
    open("/dev/null") as f13,
    open("/dev/null") as f14,
    open("/dev/null") as f15,
    open("/dev/null") as f16,
    open("/dev/null") as f17,
    open("/dev/null") as f18,
    open("/dev/null") as f19,
    open("/dev/null") as f20,
    open("/dev/null") as f21,
):
    print(f0.closed)
