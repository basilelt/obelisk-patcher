#!/usr/bin/env python3
"""Unit tests for tools/patch_manifest.py."""

import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from tools.patch_manifest import (
    ATTR_DEBUGGABLE_RES_ID,
    parse_string_pool,
    patch_apk,
    patch_manifest_axml,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_APK = os.path.join(REPO_ROOT, "input", "base.apk")


class TestPatchManifest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.zin = zipfile.ZipFile(BASE_APK, "r")
        self.orig_manifest = self.zin.read("AndroidManifest.xml")

    def tearDown(self):
        self.zin.close()
        shutil.rmtree(self.tmpdir)

    def test_patch_raw_axml(self):
        """Test patching raw AXML manifest bytes."""
        patched = patch_manifest_axml(self.orig_manifest)
        self.assertGreater(len(patched), len(self.orig_manifest))

        # Check that debuggable is present in string pool
        sp = parse_string_pool(patched, 8)
        self.assertIn("debuggable", sp["strings"])
        debug_idx = sp["strings"].index("debuggable")

        # Verify resource map entry
        rm_pos = 8 + sp["size"]
        rm_type, rm_hdr_size, rm_size = struct_unpack_rm_hdr(patched, rm_pos)
        self.assertEqual(rm_type, 0x0180)
        res_ids = struct_unpack_res_ids(patched, rm_pos + rm_hdr_size, (rm_size - rm_hdr_size) // 4)
        self.assertEqual(res_ids[debug_idx], ATTR_DEBUGGABLE_RES_ID)

    def test_idempotent_patch(self):
        """Test patching an already-patched manifest updates in-place without error."""
        patched1 = patch_manifest_axml(self.orig_manifest)
        patched2 = patch_manifest_axml(patched1)
        self.assertEqual(len(patched1), len(patched2))

    def test_patch_apk(self):
        """Test patching an entire APK."""
        out_apk = os.path.join(self.tmpdir, "base.unsigned.apk")
        patch_apk(BASE_APK, out_apk)
        self.assertTrue(os.path.exists(out_apk))

        with zipfile.ZipFile(out_apk, "r") as zout:
            # META-INF should be stripped
            for name in zout.namelist():
                self.assertFalse(name.startswith("META-INF/"), f"META-INF file not stripped: {name}")

            # AndroidManifest.xml should be patched
            manifest = zout.read("AndroidManifest.xml")
            sp = parse_string_pool(manifest, 8)
            self.assertIn("debuggable", sp["strings"])


def struct_unpack_rm_hdr(data, pos):
    import struct
    return struct.unpack_from("<HHI", data, pos)


def struct_unpack_res_ids(data, pos, count):
    import struct
    return list(struct.unpack_from(f"<{count}I", data, pos))


if __name__ == "__main__":
    unittest.main()
