"""Offline scalar inference: run.py MODEL.weights CASE.input [--full] [--loss]."""
from driver import main
from ndarray import matmul

main(matmul)
