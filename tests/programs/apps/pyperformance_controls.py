# Separate correctness controls: benchmark timing inputs and regions stay unchanged.
from fannkuch import fannkuch
from scimark import Array2D, SOR_execute, SparseCompRow_matmult

for size in range(2, 8):
    print("fannkuch", size, fannkuch(size))

# Nonuniform data makes the SOR interior change. Print every cell, including boundaries.
data = [[1.0, 2.0, 4.0, 8.0], [16.0, 0.0, 2.0, 3.0],
        [5.0, 7.0, 1.0, 6.0], [9.0, 10.0, 11.0, 12.0]]
for cycles in [0, 1, 3]:
    grid = Array2D(4, 4, data)
    SOR_execute(1.25, grid, cycles, None)
    print("SOR", cycles, grid.data)

# Unequal row lengths, an empty row, nontrivial column indices and signed values.
for cycles in [0, 1, 3]:
    result = [99.0] * 4
    checksum = SparseCompRow_matmult(4, result, [2.0, -1.0, 0.5, 3.0, -2.0, 4.0],
                                   [0, 2, 2, 5, 6], [0, 3, 0, 1, 3, 2],
                                   [1.0, 2.0, 3.0, 4.0], cycles)
    print("sparse", cycles, result, checksum)
