# pyaes 1.6.1

Compile the pure-Python AES block cipher: key expansion for 128-, 192- and 256-bit keys, and encryption/decryption of one 16-byte block.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/pyaes/) · [License](LICENSE)

```python
from pyaes import AES

cipher = AES([0] * 16)
encrypted = cipher.encrypt([0] * 16)
print(cipher.decrypt(encrypted))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `AES(key)`, `encrypt(block)` and `decrypt(block)`, with `list[int]` keys and blocks. Use values from 0 to 255 to represent bytes.
- Key lengths are 16, 24 or 32; blocks contain 16 integers.
- The packaged mode classes, `Counter`, streaming API, padding and `AESModesOfOperation` are outside the validated port coverage. A mode can be built directly on `AES`.

<a id="deviations-it-hits"></a>

## Compatibility

- The adapted constructor does not check that each integer is in 0..255. Values outside that range can produce upstream-style unusual results or overflow.
- ASCII text can be converted with `ord()`; iterating non-ASCII text produces UTF-8 bytes rather than CPython characters.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/port_pyaes_cipher.py
./tests/run.sh ./pystachy "jit aot" tests/port_pyaes_cipher.py
```

The differential program checks FIPS-197, NIST SP 800-38A and OpenSSL IGE vectors, all key sizes, round keys, repeated round trips and invalid sizes.

Cases: [port_pyaes_cipher.py](../../tests/port_pyaes_cipher.py).

<a id="speed"></a>

## Performance snapshot

The recorded counter-block workload was about **44× faster** by CPU time than CPython 3.13.16 on upstream (**34×** by wall time). The OpenSSL comparison makes one block call at a time; it does not measure bulk AES throughput.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from pyaes 1.6.1; license: MIT.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="pyaes-161-ported-to-pystachy"></a>
