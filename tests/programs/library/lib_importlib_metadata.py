# importlib.metadata: version(), metadata(), requires() and distribution() of the dist-info and
# egg-info directories on the module path (tests/metadata_packages), and what a metadata
# message answers.
import importlib.metadata
from importlib.metadata import Distribution, PackageMetadata, PathDistribution, distribution, metadata, requires, version

print(version("demo-pkg"), version("Demo.Pkg"), version("demo__pkg"), version("DEMO_PKG"), version("demo-_.pkg"))
print(importlib.metadata.version("distinfo-pkg"), version("egginfo-pkg"), version("egginfo_file"))

md = metadata("demo_pkg")
print(type(md).__name__, len(md), md["name"], md["NAME"], md["Metadata-Version"])
print(md.keys())
print(md.values())
print(md.items()[:3])
print([key for key in md][-4:])
print(repr(md["Summary"]), repr(md["License"]))
print(repr(md["Author"]), repr(md["Home-page"]), repr(md["Empty"]))
print(repr(md["Description"]))
print(md.get_all("classifier"), md.get_all("Classifier"), md.get_all("nothing"), md.get_all("nothing", ["x"]))
print(md.get("VERSION"), md.get("nothing"), md.get("nothing", "fallback"))
print("License" in md, "license" in md, "Licence" in md, "Description" in md, "" in md)


def show(message: PackageMetadata) -> str:
    return message["Name"] + " " + message["Version"]


print(show(md), show(metadata("egginfo-pkg")))

d = distribution("egginfo-pkg")
print(type(d).__name__, isinstance(d, Distribution), isinstance(d, PathDistribution))
print(d.name, d.version, d.metadata["Author"], d.metadata.get_all("Classifier"))
print(repr(d.metadata["Description"]), "Description" in d.metadata.keys())
print(repr(d.read_text("top_level.txt")), d.read_text("missing.txt"), d.read_text("PKG-INFO") == d.read_text("PKG-INFO"))
print(d.requires)
print(Distribution.from_name("pkg-dot").version, PathDistribution.from_name("pkg.dot").name)

print(requires("demo-pkg"))
print(requires("distinfo-pkg"))
print(requires("complex-deps"))
print(requires("emptyreq"), requires("egginfo_file"), requires("pkg.dot"))
other = distribution("egginfo_file")
print(other.metadata.items())
print(version("fallback-pkg"), metadata("fallback_pkg").keys())
