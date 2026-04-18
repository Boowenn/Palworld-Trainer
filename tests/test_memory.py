"""Pure unit tests for the memory module.

These exercise the parts that don't touch a live Windows process — AOB
pattern compilation, float packing, aligned-match iteration, and scan
snapshot invariants. The live RPM/WPM round-trip is covered by an
optional in-process smoke test in ``test_mem_engine_live.py``.
"""

from __future__ import annotations

import struct
import unittest

from tests import _bootstrap  # noqa: F401

from palworld_trainer import memory as mem


class ParseAobTests(unittest.TestCase):
    def test_hex_bytes_only(self) -> None:
        raw, regex = mem.parse_aob("AA BB CC")
        self.assertEqual(raw, b"\xaa\xbb\xcc")
        self.assertIsNotNone(regex.match(b"\xaa\xbb\xcc"))

    def test_wildcards_question_marks(self) -> None:
        raw, regex = mem.parse_aob("48 8B ?? F0 ??")
        self.assertEqual(len(raw), 5)
        # Zero byte placeholder for wildcards
        self.assertEqual(raw[2], 0)
        # Wildcard positions match any byte
        self.assertIsNotNone(regex.match(b"\x48\x8b\xff\xf0\x99"))
        self.assertIsNotNone(regex.match(b"\x48\x8b\x00\xf0\x00"))
        # Non-wildcard position must still match literally
        self.assertIsNone(regex.match(b"\x48\x99\xff\xf0\x99"))

    def test_single_question_mark_same_as_double(self) -> None:
        _raw1, r1 = mem.parse_aob("? CC")
        _raw2, r2 = mem.parse_aob("?? CC")
        # Both regexes should match the same input
        self.assertIsNotNone(r1.match(b"\x11\xcc"))
        self.assertIsNotNone(r2.match(b"\x11\xcc"))


class PackingTests(unittest.TestCase):
    def test_pack_f32_matches_struct(self) -> None:
        self.assertEqual(mem.pack_f32(1.5), struct.pack("<f", 1.5))
        self.assertEqual(mem.pack_f32(0.0), b"\x00\x00\x00\x00")

    def test_pack_i32_matches_struct(self) -> None:
        self.assertEqual(mem.pack_i32(0), b"\x00\x00\x00\x00")
        self.assertEqual(mem.pack_i32(-1), b"\xff\xff\xff\xff")


class AlignedMatchTests(unittest.TestCase):
    def test_returns_aligned_hits(self) -> None:
        needle = mem.pack_f32(9999.0)  # 4 bytes, arbitrary value
        # Build a buffer with the needle at offsets 0, 4, 12 (all aligned)
        chunk = needle + needle + b"\x00\x00\x00\x00" + needle
        hits = list(mem._iter_exact_matches(chunk, needle))
        self.assertEqual(hits, [0, 4, 12])

    def test_skips_unaligned_hits(self) -> None:
        needle = mem.pack_f32(123.0)
        # Stick the needle at offset 1 (unaligned) — should not appear.
        chunk = b"\x00" + needle + b"\x00\x00\x00"
        self.assertEqual(list(mem._iter_exact_matches(chunk, needle)), [])


class ScanSnapshotTests(unittest.TestCase):
    def test_len_and_fields(self) -> None:
        snap = mem.ScanSnapshot(addresses=[0x1000, 0x2000], value=500.0, kind="f32")
        self.assertEqual(len(snap), 2)
        self.assertEqual(snap.value, 500.0)
        self.assertEqual(snap.kind, "f32")


if __name__ == "__main__":
    unittest.main()
