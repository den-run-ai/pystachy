"""Publish the two tested native images as one immutable Docker version.

Run after loading pystachy:release-test-amd64 and pystachy:release-test-arm64.
Authentication stays in the caller's Docker configuration. Pull requests never
invoke publication; tests exercise the registry decisions with synthetic data.
"""

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request

ARCHITECTURES = ("amd64", "arm64")
INDEX_TYPES = ("application/vnd.oci.image.index.v1+json",
               "application/vnd.docker.distribution.manifest.list.v2+json")


def command(arguments):
    return subprocess.run(arguments, capture_output=True, text=True, check=True, timeout=600).stdout.strip()


def digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise RuntimeError("Docker metadata has no valid SHA-256 digest")
    return value


def registry_manifest(reference):
    descriptor = json.loads(command(["docker", "buildx", "imagetools", "inspect", reference,
                                     "--format", "{{json .Manifest}}"] ))
    value = digest(descriptor.get("digest"))
    immutable = reference.split("@", 1)[0] + "@" + value
    manifest = json.loads(command(["docker", "buildx", "imagetools", "inspect", immutable, "--raw"]))
    manifest["digest"] = value
    return manifest


def image_labels(config, architecture, version, commit):
    labels = config.get("config", {}).get("Labels", {})
    if (config.get("os") != "linux" or config.get("architecture") != architecture
            or labels.get("org.opencontainers.image.version") != version
            or labels.get("org.opencontainers.image.revision") != commit):
        raise RuntimeError("Docker image platform or release labels do not match the release")


def index_images(manifest):
    """Require precisely the supported native platforms; reject duplicates."""
    if manifest.get("mediaType") not in INDEX_TYPES or manifest.get("schemaVersion") != 2:
        raise RuntimeError("Docker release must be a multiarchitecture image index")
    images = {}
    for entry in manifest.get("manifests", []):
        platform = entry.get("platform", {})
        architecture = platform.get("architecture")
        variants = (None, "", "v8") if architecture == "arm64" else (None, "")
        if (platform.get("os") != "linux" or architecture not in ARCHITECTURES
                or platform.get("variant") not in variants or architecture in images):
            raise RuntimeError("Docker release has an unexpected or duplicated platform")
        images[architecture] = digest(entry.get("digest"))
    if set(images) != set(ARCHITECTURES):
        raise RuntimeError("Docker release must include linux/amd64 and linux/arm64")
    return images


def verified_source(image, version, commit):
    """Return an immutable reference after checking every platform's labels.

    Historical single-platform amd64 releases remain promotable. New publication
    always requires both architectures through index_images().
    """
    source = image + ":" + version
    manifest = registry_manifest(source)
    immutable = image + "@" + digest(manifest.get("digest"))
    if manifest.get("mediaType") in INDEX_TYPES:
        sources = {architecture: image + "@" + value for architecture, value in index_images(manifest).items()}
    else:
        sources = {"amd64": immutable}
    for architecture, reference in sources.items():
        config = json.loads(command(["docker", "buildx", "imagetools", "inspect", reference,
                                     "--format", "{{json .Image}}"] ))
        image_labels(config, architecture, version, commit)
    return immutable


def hub_metadata(image, suffix="", missing_ok=False):
    try:
        with urllib.request.urlopen("https://hub.docker.com/v2/repositories/" + image + "/" + suffix,
                                    timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        raise RuntimeError(f"Docker Hub returned HTTP {error.code}") from None


def local_images(version, commit):
    images = {}
    for architecture in ARCHITECTURES:
        reference = "pystachy:release-test-" + architecture
        config = json.loads(command(["docker", "image", "inspect", reference]))
        if len(config) != 1:
            raise RuntimeError("Expected one loaded image per architecture")
        config = config[0]
        image_labels({"os": config.get("Os"), "architecture": config.get("Architecture"),
                      "config": config.get("Config", {})}, architecture, version, commit)
        images[architecture] = digest(config.get("Id"))
    return images


def matching_image(reference, expected):
    manifest = registry_manifest(reference)
    if manifest.get("config", {}).get("digest") != expected:
        raise RuntimeError("Docker version already exists with different contents; choose a new version")
    return digest(manifest.get("digest"))


def publish(image, version, commit):
    tested = local_images(version, commit)
    if hub_metadata(image).get("is_private") is not False:
        raise RuntimeError("Create a public Docker Hub repository before publishing")
    source = image + ":" + version
    if hub_metadata(image, "tags/" + version + "/", missing_ok=True) is not None:
        # Check every architecture without pulling/running foreign code, and do
        # not replace an existing version with a different image or platform set.
        manifest = registry_manifest(source)
        for architecture, value in index_images(manifest).items():
            matching_image(image + "@" + value, tested[architecture])
        print("Existing Docker version matches both tested native images")
        return
    existing = {}
    for architecture in ARCHITECTURES:
        tag = version + "-" + architecture
        if hub_metadata(image, "tags/" + tag + "/", missing_ok=True) is not None:
            existing[architecture] = matching_image(image + ":" + tag, tested[architecture])
    # Finish all immutable-version checks before the first push. A retry can
    # reuse one architecture left by an interrupted publication.
    for architecture in ARCHITECTURES:
        if architecture not in existing:
            target = source + "-" + architecture
            command(["docker", "tag", "pystachy:release-test-" + architecture, target])
            command(["docker", "push", target])
            existing[architecture] = matching_image(target, tested[architecture])
    command(["docker", "buildx", "imagetools", "create", "--tag", source,
             *(image + "@" + existing[architecture] for architecture in ARCHITECTURES)])
    if index_images(registry_manifest(source)) != existing:
        raise RuntimeError("Published Docker index differs from the tested native images")
    print(f"Published {source}: linux/amd64 and linux/arm64")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*", args.image):
        parser.error("image must be namespace/repository")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?", args.version):
        parser.error("version must be a v-prefixed semantic version")
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("commit must be a full Git commit SHA")
    try:
        publish(args.image, args.version, args.commit)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"release images: {error.cmd[0]} exited {error.returncode}\n")
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"release images: {error}\n")


if __name__ == "__main__":
    main()
