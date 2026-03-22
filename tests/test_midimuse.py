#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from midimuse import ALBUM, GENRES, build_album, compose, encode_varlen, synth_track


class MidiMuseTests(unittest.TestCase):
    def test_varlen_encoding(self) -> None:
        self.assertEqual(encode_varlen(0), b"\x00")
        self.assertEqual(encode_varlen(127), b"\x7f")
        self.assertEqual(encode_varlen(128), b"\x81\x00")

    def test_compose_starts_with_midi_header(self) -> None:
        payload = compose("ambient", 8, 3, "test-song")
        self.assertTrue(payload.startswith(b"MThd"))

    def test_all_genres_render(self) -> None:
        for genre in GENRES:
            payload = compose(genre, 4, 5, genre)
            self.assertIn(b"MTrk", payload)
            self.assertGreater(len(payload), 100)

    def test_drums_change_track_count(self) -> None:
        ambient = compose("ambient", 4, 1, "ambient")
        techno = compose("techno", 4, 1, "techno")
        self.assertGreater(len(techno), len(ambient))

    def test_build_album_outputs_manifest_and_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = build_album(Path(tmpdir))
            self.assertEqual(manifest["title"], ALBUM.title)
            self.assertTrue((Path(tmpdir) / "cover.svg").exists())
            self.assertTrue((Path(tmpdir) / "index.html").exists())
            self.assertTrue((Path(tmpdir) / "album.json").exists())
            self.assertEqual(len(list((Path(tmpdir) / "songs").glob("*.mid"))), 10)
            self.assertEqual(len(list((Path(tmpdir) / "songs").glob("*.wav"))), 10)

    def test_synth_track_outputs_wav(self) -> None:
        payload = synth_track("ambient", 4, 1)
        self.assertTrue(payload.startswith(b"RIFF"))


if __name__ == "__main__":
    unittest.main()
