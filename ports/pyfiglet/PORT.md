# pyfiglet 1.0.4

Render text as ASCII banners using the embedded `standard`, `slant` and `small` fonts, including wrapping, kerning, smushing and justification.

[All ports](../README.md) · [Source](__init__.py) · [Upstream](https://pypi.org/project/pyfiglet/) · [License](LICENSE)

```python
from pyfiglet import figlet_format

print(figlet_format("Hi", font="small", width=80))
```

<a id="what-compiles-as-it-is"></a>
<a id="what-the-port-leaves-out"></a>

## Coverage

- `figlet_format()` and `Figlet.renderText()`; `Figlet.setFont(font=...)` switches among the three embedded fonts.
- `direction`, `justify` and `width` keyword arguments, which `figlet_format()` passes on to `Figlet` as upstream does. Rendering returns a plain `str`; `Figlet.direction` and `Figlet.justify` are read-only properties.
- Font discovery/installation, external or zipped fonts, color helpers, CLI and `FigletString` transformations are outside this port’s coverage.

<a id="deviations-it-hits"></a>

## Compatibility

- A helper decodes UTF-8 input into characters before selecting glyphs. Unsupported glyphs are skipped as upstream does. Only ASCII-drawn fonts are embedded.
- `setFont()` takes its font as a `str` keyword argument, as upstream reads it; `setFont(font=None)`, on which upstream fails, is a compile-time error.
- Until the re-baseline (#262), the port took `figlet_format()`'s and `setFont()`'s arguments by position too, and had `direction()` and `justify()` methods; such calls, which upstream rejects, are now compile-time errors.
- Very large widths can overflow or exhaust native memory; measuring output strings still counts UTF-8 bytes.

<a id="tests"></a>

## Run and validate

From the repository root, after building the compiler:

```sh
PYSTACHY_PATH=ports ./pystachy run tests/programs/apps/port_pyfiglet_render.py
./tests/run.sh ./pystachy "jit aot" tests/programs/apps/port_pyfiglet_render.py tests/programs/apps/port_pyfiglet_edges.py
```

The tests cover upstream banner examples, all three fonts, wrapping/justification, right-to-left output, glyph parsing, Unicode input and errors.

Cases: [port_pyfiglet_render.py](../../tests/programs/apps/port_pyfiglet_render.py), [port_pyfiglet_edges.py](../../tests/programs/apps/port_pyfiglet_edges.py).

<a id="speed"></a>

## Performance snapshot

Recorded AOT runs were about **2.7× faster** than CPython 3.13.16 on upstream for both load-and-render and render-only workloads, and **2.0×** after the re-baseline, whose font parser uses upstream's regular expressions. Font loading differs: the port reads embedded strings and upstream reads files.

These are recorded port measurements, not a fresh benchmark of the current compiler.
See the [benchmark record](PORT_REFERENCE.md#benchmark-snapshot) for workloads, raw timings,
machine conditions and limitations.

<a id="the-edits-and-the-feature-each-one-stands-in-for"></a>

## Provenance

Adapted from pyfiglet 1.0.4; license: MIT; bundled FIGlet fonts: BSD-3-Clause.
Edits remain marked `# Pystachy port:` in the source. The
[port reference](PORT_REFERENCE.md) keeps upstream hashes, adaptation rationale and validation records.
Historical compiler gaps in earlier port notes are not the current language specification;
use the [language guide](../../docs/language.md) for present support.

<a id="pyfiglet-104-ported-to-pystachy"></a>
