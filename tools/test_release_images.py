"""Multiarchitecture release provenance and partial-publication recovery."""

import copy
import json
import unittest
from unittest.mock import patch

import release_images as images

IMAGE = "namespace/pystachy"
VERSION = "v0.1.0-alpha.4"
COMMIT = "a" * 40
DIGESTS = {"amd64": "sha256:" + "1" * 64, "arm64": "sha256:" + "2" * 64}
CONFIGS = {"amd64": "sha256:" + "3" * 64, "arm64": "sha256:" + "4" * 64}
INDEX_DIGEST = "sha256:" + "5" * 64


def index():
    return {"schemaVersion": 2, "mediaType": images.INDEX_TYPES[0], "digest": INDEX_DIGEST,
            "manifests": [{"digest": value, "platform": {"os": "linux", "architecture": architecture}}
                          for architecture, value in DIGESTS.items()]}


def image_config(architecture):
    return {"os": "linux", "architecture": architecture, "config": {"Labels": {
        "org.opencontainers.image.version": VERSION, "org.opencontainers.image.revision": COMMIT}}}


class ImageTests(unittest.TestCase):
    def test_index_requires_two_distinct_supported_platforms(self):
        self.assertEqual(images.index_images(index()), DIGESTS)
        for kind in ("missing", "duplicate", "foreign", "bad-digest", "big-endian", "not-index"):
            value = index()
            if kind == "missing":
                value["manifests"].pop()
            elif kind == "duplicate":
                value["manifests"].append(value["manifests"][0])
            elif kind == "foreign":
                value["manifests"][1]["platform"]["os"] = "windows"
            elif kind == "bad-digest":
                value["manifests"][1]["digest"] = "not-a-digest"
            elif kind == "big-endian":
                value["manifests"][1]["platform"]["architecture"] = "aarch64_be"
            else:
                value["mediaType"] = "application/vnd.oci.image.manifest.v1+json"
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                images.index_images(value)

    def test_registry_reads_body_at_pinned_descriptor(self):
        descriptor = {"digest": INDEX_DIGEST}
        with patch.object(images, "command", side_effect=[json.dumps(descriptor), json.dumps(index())]) as command:
            self.assertEqual(images.registry_manifest(IMAGE + ":" + VERSION), index())
        self.assertEqual(command.call_args_list[-1].args[0], ["docker", "buildx", "imagetools", "inspect",
                         IMAGE + ":" + VERSION + "@" + INDEX_DIGEST, "--raw"])

    def test_promotion_checks_both_platform_labels(self):
        configs = [image_config(architecture) for architecture in images.ARCHITECTURES]
        with patch.object(images, "registry_manifest", return_value=index()), patch.object(
                images, "command", side_effect=[json.dumps(config) for config in configs]) as command:
            self.assertEqual(images.verified_source(IMAGE, VERSION, COMMIT), IMAGE + "@" + INDEX_DIGEST)
        self.assertEqual(len(command.call_args_list), 2)
        for architecture, call in zip(images.ARCHITECTURES, command.call_args_list, strict=True):
            self.assertIn(IMAGE + "@" + DIGESTS[architecture], call.args[0])
        for key, value in (("org.opencontainers.image.revision", "b" * 40),
                           ("org.opencontainers.image.version", "v0.1.0")):
            invalid = copy.deepcopy(configs)
            invalid[1]["config"]["Labels"][key] = value
            with self.subTest(key=key), patch.object(images, "registry_manifest", return_value=index()), \
                    patch.object(images, "command", side_effect=[json.dumps(config) for config in invalid]), \
                    self.assertRaises(RuntimeError):
                images.verified_source(IMAGE, VERSION, COMMIT)

    def test_historical_single_platform_image_can_be_promoted(self):
        with patch.object(images, "registry_manifest", return_value={"digest": DIGESTS["amd64"]}), \
                patch.object(images, "command", return_value=json.dumps(image_config("amd64"))):
            self.assertEqual(images.verified_source(IMAGE, VERSION, COMMIT), IMAGE + "@" + DIGESTS["amd64"])

    def test_loaded_images_must_match_architecture_commit_and_version(self):
        configs = [{"Os": "linux", "Architecture": architecture, "Id": CONFIGS[architecture],
                    "Config": image_config(architecture)["config"]} for architecture in images.ARCHITECTURES]
        with patch.object(images, "command", side_effect=[json.dumps([config]) for config in configs]):
            self.assertEqual(images.local_images(VERSION, COMMIT), CONFIGS)
        configs[1]["Architecture"] = "amd64"
        with patch.object(images, "command", side_effect=[json.dumps([config]) for config in configs]), \
                self.assertRaises(RuntimeError):
            images.local_images(VERSION, COMMIT)

    def test_existing_version_verifies_both_contents_without_writing(self):
        with patch.object(images, "local_images", return_value=CONFIGS), patch.object(
                images, "hub_metadata", side_effect=[{"is_private": False}, {}]), patch.object(
                images, "registry_manifest", return_value=index()), patch.object(
                images, "matching_image", side_effect=list(DIGESTS.values())) as matching, patch.object(
                images, "command") as command:
            images.publish(IMAGE, VERSION, COMMIT)
        command.assert_not_called()
        self.assertEqual([call.args for call in matching.call_args_list],
                         [(IMAGE + "@" + DIGESTS[architecture], CONFIGS[architecture]) for architecture in images.ARCHITECTURES])

    def test_partial_publication_reuses_matching_native_image(self):
        with patch.object(images, "local_images", return_value=CONFIGS), patch.object(
                images, "hub_metadata", side_effect=[{"is_private": False}, None, {}, None]), patch.object(
                images, "matching_image", side_effect=[DIGESTS["amd64"], DIGESTS["arm64"]]), patch.object(
                images, "registry_manifest", return_value=index()), patch.object(images, "command") as command:
            images.publish(IMAGE, VERSION, COMMIT)
        calls = [call.args[0] for call in command.call_args_list]
        self.assertEqual(calls, [
            ["docker", "tag", "pystachy:release-test-arm64", IMAGE + ":" + VERSION + "-arm64"],
            ["docker", "push", IMAGE + ":" + VERSION + "-arm64"],
            ["docker", "buildx", "imagetools", "create", "--tag", IMAGE + ":" + VERSION,
             IMAGE + "@" + DIGESTS["amd64"], IMAGE + "@" + DIGESTS["arm64"]]])

    def test_mismatched_existing_architecture_blocks_all_pushes(self):
        with patch.object(images, "local_images", return_value=CONFIGS), patch.object(
                images, "hub_metadata", side_effect=[{"is_private": False}, None, None, {}]), patch.object(
                images, "matching_image", side_effect=RuntimeError("different contents")), patch.object(
                images, "command") as command, self.assertRaises(RuntimeError):
            images.publish(IMAGE, VERSION, COMMIT)
        command.assert_not_called()

    def test_same_labels_with_different_config_cannot_replace_a_version(self):
        with patch.object(images, "registry_manifest", return_value={"digest": DIGESTS["amd64"],
                "config": {"digest": CONFIGS["arm64"]}}), self.assertRaisesRegex(RuntimeError, "different contents"):
            images.matching_image(IMAGE, CONFIGS["amd64"])


if __name__ == "__main__":
    unittest.main()
