"""Small deterministic numeric inputs, including nonzero SciMark controls."""
import math
import pytest

import barnes_hut
import chaos
import float as floating
import nbody
import raytrace
import scimark
import spectral_norm


def test_barnes_hut():
    energy = barnes_hut.bench_quadtree_nbody(1, 8, 2, barnes_hut.DEFAULT_THETA)
    assert math.isclose(energy, 84.91499997657874, rel_tol=1e-12)


def test_chaos():
    image = chaos.main().create_image_chaos(20, 20, 20, None, chaos.DEFAULT_RNG_SEED)
    assert len(image) == 20
    assert all(len(column) == 20 for column in image)
    assert sum(sum(column) for column in image) == 382


def test_float():
    point = floating.benchmark(10)
    assert math.isclose(point.x, 0.8335183971759773, rel_tol=1e-12)
    assert point.y == 1.0
    assert math.isclose(point.z, 0.4123241499791782, rel_tol=1e-12)


@pytest.fixture
def bodies():
    # Preserve the mutable module state after the test, including failed assertions.
    positions = [body[0][:] for body in nbody.SYSTEM]
    velocities = [body[1][:] for body in nbody.SYSTEM]
    yield nbody.SYSTEM
    for index in range(len(nbody.SYSTEM)):
        nbody.SYSTEM[index][0][:] = positions[index]
        nbody.SYSTEM[index][1][:] = velocities[index]


def test_nbody(bodies):
    assert bodies is nbody.SYSTEM
    assert math.isclose(nbody.bench_nbody(1, nbody.DEFAULT_REFERENCE, 100),
                        -0.1690507623824095, rel_tol=1e-12)


def test_raytrace():
    assert raytrace.bench_raytrace(1, 10, 10, None) == 13468


def test_spectral_norm():
    assert math.isclose(spectral_norm.bench_spectral_norm(1), 1.6236422398020804, rel_tol=1e-12)


@pytest.mark.parametrize("cycles", [0, 1, 3])
def test_scimark_sparse(cycles: int):
    result = [99.0] * 4
    checksum = scimark.SparseCompRow_matmult(
        4, result, [2.0, -1.0, 0.5, 3.0, -2.0, 4.0], [0, 2, 2, 5, 6], [0, 3, 0, 1, 3, 2],
        [1.0, 2.0, 3.0, 4.0], cycles,
    )
    assert result == ([99.0, 99.0, 99.0, 99.0] if cycles == 0 else [-2.0, 0.0, -1.5, 12.0])
    assert checksum == (396.0 if cycles == 0 else 8.5)


def test_scimark_sor():
    grid = scimark.Array2D(3, 3, [[1.0, 2.0, 3.0], [4.0, 0.0, 6.0], [7.0, 8.0, 9.0]])
    scimark.SOR_execute(1.25, grid, 1, None)
    assert grid.data == [1.0, 2.0, 3.0, 4.0, 6.25, 6.0, 7.0, 8.0, 9.0]


def test_scimark_fft_lu_monte_carlo():
    assert math.isclose(scimark.bench_FFT(1, 16, 2), 14.879124534260074, rel_tol=1e-12)
    assert math.isclose(scimark.bench_LU(1, 5), 21.760385308388017, rel_tol=1e-12)
    assert scimark.bench_MonteCarlo(1, 100) == 3.16
