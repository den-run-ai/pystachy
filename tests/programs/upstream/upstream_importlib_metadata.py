# Adapted from CPython 3.13.16 Lib/test/test_importlib/metadata/test_api.py (SHA-256
# d536972b648e550165e4390db385a4ed29d72a5d45e4fbb9a9939844f253398f). PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# These sixteen methods of APITests and LegacyDots retain every assertion; only unittest
# scaffolding becomes ordinary assertions, and an "is not None" assertion precedes the uses of
# a result that may be None. Upstream builds each distribution in a temporary
# directory that it adds to sys.path; a compiled program's module path is fixed when it is
# compiled, so the same files lie in tests/metadata_packages/site, written from the texts of
# fixtures.py (SHA-256 5c2303d0c54e21169d1817612b80f9141c793209cb177cee0dcb45fe6162c1b0):
# EggInfoPkg, EggInfoPkgPipInstalledNoModules, DistInfoPkg, DistInfoPkgWithDot, EggInfoFile
# and DistInfoPkgWithDotLegacy's pkg.lot.egg-info. test_requires_egg_info_empty and
# test_more_complex_deps_requires_text read a requires.txt of their own distribution
# (emptyreq, complex-deps) where upstream rewrites egginfo-pkg's or calls the private parser.
# Not adapted: the entry point, file and JSON methods (entry_points(), files() and
# PackageMetadata.json are not provided), test_missing_key_legacy (a missing key raises
# KeyError: tests/deviations/lib_importlib_metadata_missing_key.py), OffSysPathTests
# (Distribution.discover() and at()) and InvalidateCache. The .out is recorded with CPython's
# stdlib; JIT/AOT use lib/importlib/metadata.py.
import re
from importlib.metadata import PackageNotFoundError, distribution, metadata, requires, version

version_pattern = r'\d+\.\d+(\.\d)?'


# test_api.APITests.test_retrieves_version_of_self
def test_retrieves_version_of_self() -> None:
    pkg_version = version('egginfo-pkg')
    assert isinstance(pkg_version, str)
    assert re.match(version_pattern, pkg_version)
    print('APITests.test_retrieves_version_of_self', pkg_version)


# test_api.APITests.test_retrieves_version_of_distinfo_pkg
def test_retrieves_version_of_distinfo_pkg() -> None:
    pkg_version = version('distinfo-pkg')
    assert isinstance(pkg_version, str)
    assert re.match(version_pattern, pkg_version)
    print('APITests.test_retrieves_version_of_distinfo_pkg', pkg_version)


# test_api.APITests.test_for_name_does_not_exist
def test_for_name_does_not_exist() -> None:
    try:
        distribution('does-not-exist')
        raise AssertionError('PackageNotFoundError not raised')
    except PackageNotFoundError:
        pass
    print('APITests.test_for_name_does_not_exist', 1)


# test_api.APITests.test_name_normalization
def test_name_normalization() -> None:
    names = 'pkg.dot', 'pkg_dot', 'pkg-dot', 'pkg..dot', 'Pkg.Dot'
    for name in names:
        assert distribution(name).metadata['Name'] == 'pkg.dot'
    print('APITests.test_name_normalization', len(names))


# test_api.APITests.test_prefix_not_matched
def test_prefix_not_matched() -> None:
    prefixes = 'p', 'pkg', 'pkg.'
    for prefix in prefixes:
        try:
            distribution(prefix)
            raise AssertionError('PackageNotFoundError not raised')
        except PackageNotFoundError:
            pass
    print('APITests.test_prefix_not_matched', len(prefixes))


# test_api.APITests.test_for_top_level
def test_for_top_level() -> None:
    tests = [
        ('egginfo-pkg', 'mod'),
        ('egg_with_no_modules-pkg', ''),
    ]
    for pkg_name, expect_content in tests:
        text = distribution(pkg_name).read_text('top_level.txt')
        assert text is not None
        assert text.strip() == expect_content
    print('APITests.test_for_top_level', len(tests))


# test_api.APITests.test_metadata_for_this_package
def test_metadata_for_this_package() -> None:
    md = metadata('egginfo-pkg')
    assert md['author'] == 'Steven Ma'
    assert md['LICENSE'] == 'Unknown'
    assert md['Name'] == 'egginfo-pkg'
    classifiers = md.get_all('Classifier')
    assert classifiers is not None
    assert 'Topic :: Software Development :: Libraries' in classifiers
    print('APITests.test_metadata_for_this_package', 4)


# test_api.APITests.test_get_key
def test_get_key() -> None:
    md = metadata('egginfo-pkg')
    assert md.get('Name') == 'egginfo-pkg'
    print('APITests.test_get_key', 1)


# test_api.APITests.test_get_missing_key
def test_get_missing_key() -> None:
    md = metadata('distinfo-pkg')
    assert md.get('does-not-exist') is None
    print('APITests.test_get_missing_key', 1)


# test_api.APITests.test_version_egg_info_file
def test_version_egg_info_file() -> None:
    assert version('egginfo-file') == '0.1'
    print('APITests.test_version_egg_info_file', 1)


# test_api.APITests.test_requires_egg_info_file
def test_requires_egg_info_file() -> None:
    requirements = requires('egginfo-file')
    assert requirements is None
    print('APITests.test_requires_egg_info_file', 1)


# test_api.APITests.test_requires_egg_info
def test_requires_egg_info() -> None:
    deps = requires('egginfo-pkg')
    assert deps is not None
    assert len(deps) == 2
    assert any(dep == 'wheel >= 1.0; python_version >= "2.7"' for dep in deps)
    print('APITests.test_requires_egg_info', 2)


# test_api.APITests.test_requires_egg_info_empty
def test_requires_egg_info_empty() -> None:
    deps = requires('emptyreq')
    assert deps == []
    print('APITests.test_requires_egg_info_empty', 1)


# test_api.APITests.test_requires_dist_info
def test_requires_dist_info() -> None:
    deps = requires('distinfo-pkg')
    assert deps is not None
    assert len(deps) == 2
    assert all(deps)
    assert 'wheel >= 1.0' in deps
    assert "pytest; extra == 'test'" in deps
    print('APITests.test_requires_dist_info', 4)


# test_api.APITests.test_more_complex_deps_requires_text
def test_more_complex_deps_requires_text() -> None:
    found = requires('complex-deps')
    assert found is not None
    deps = sorted(found)
    expected = [
        'dep1',
        'dep2',
        'dep3; python_version < "3"',
        'dep4; extra == "extra1"',
        'dep5; (python_version < "3") and extra == "extra2"',
        'dep6@ git+https://example.com/python/dep.git@v1.0.0 ; extra == "extra1"',
    ]
    # It's important that the environment marker expression be
    # wrapped in parentheses to avoid the following 'and' binding more
    # tightly than some other part of the environment expression.

    assert deps == expected
    print('APITests.test_more_complex_deps_requires_text', len(expected))


# test_api.LegacyDots.test_name_normalization_versionless_egg_info
def test_name_normalization_versionless_egg_info() -> None:
    names = 'pkg.lot', 'pkg_lot', 'pkg-lot', 'pkg..lot', 'Pkg.Lot'
    for name in names:
        assert distribution(name).metadata['Name'] == 'pkg.lot'
    print('LegacyDots.test_name_normalization_versionless_egg_info', len(names))


test_retrieves_version_of_self()
test_retrieves_version_of_distinfo_pkg()
test_for_name_does_not_exist()
test_name_normalization()
test_prefix_not_matched()
test_for_top_level()
test_metadata_for_this_package()
test_get_key()
test_get_missing_key()
test_version_egg_info_file()
test_requires_egg_info_file()
test_requires_egg_info()
test_requires_egg_info_empty()
test_requires_dist_info()
test_more_complex_deps_requires_text()
test_name_normalization_versionless_egg_info()
