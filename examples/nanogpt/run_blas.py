"""Offline BLAS inference: run_blas.py MODEL.weights CASE.input [--full] [--loss]."""
from driver import main
from ndarray_blas import linear, matmul

main(matmul, linear)
