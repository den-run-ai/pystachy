# iniconfig 2.3.1

Read INI files such as `pytest.ini`, `tox.ini` and `setup.cfg` with section access and source-line reporting.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/iniconfig/) · [License](LICENSE)

```python
from iniconfig import IniConfig

config = IniConfig("demo.ini", data="[app]\nname = demo\n")
print(config["app"]["name"])
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `IniConfig`, section lookup and iteration, `get()`, `lineof()`, comments and parse errors.
- `get()` takes `default=` and `convert=`. Without a conversion the default is a string or `None`; with one, it is `None` or of the converted type, as each call's result has one type.
- `SectionWrapper.items()` returns a list of pairs rather than a generator.

<a id="deviations-it-hits"></a>

## Compatibility

The retained parsing and string-access API follows upstream. Calls with unsupported argument types are compile-time errors. Iteration keeps source-line order.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/programs/apps/port_iniconfig_parse.py
./tests/run.sh ./pystachy "jit aot" tests/programs/apps/port_iniconfig_parse.py tests/programs/apps/port_iniconfig_api.py
```

The differential programs adapt upstream’s parsing/API tests and compare printed results with CPython through JIT and AOT.

Cases: [port_iniconfig_parse.py](../../tests/programs/apps/port_iniconfig_parse.py), [port_iniconfig_api.py](../../tests/programs/apps/port_iniconfig_api.py).

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from iniconfig 2.3.1; license: MIT.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="iniconfig-231-ported-to-pystachy"></a>
