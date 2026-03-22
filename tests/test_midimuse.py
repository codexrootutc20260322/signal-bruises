#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from midimuse import (
    ALBUM,
    EP,
    AlbumSpec,
    GENRES,
    TrackSpec,
    build_album,
    build_release,
    compose,
    encode_varlen,
    lyric_lines,
    synth_track,
)


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

    def test_build_release_outputs_manifest_tracks_and_lyrics(self) -> None:
        sample_release = AlbumSpec(
            title="Test EP",
            artist="codexrootutc20260322",
            subtitle="small release for validation",
            palette=("#000000", "#111111", "#eeeeee", "#ff9900"),
            release_type="ep",
            tracks=[
                TrackSpec("Alpha", "ambient", 4, 3, "alpha line"),
                TrackSpec("Beta", "lofi", 4, 5, "beta line", language="es"),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = build_release(sample_release, Path(tmpdir))
            self.assertEqual(manifest["title"], sample_release.title)
            self.assertEqual(manifest["release_type"], "ep")
            self.assertTrue((Path(tmpdir) / "cover.svg").exists())
            self.assertTrue((Path(tmpdir) / "index.html").exists())
            self.assertTrue((Path(tmpdir) / "album.json").exists())
            self.assertEqual(len(list((Path(tmpdir) / "songs").glob("*.mid"))), 2)
            self.assertEqual(len(list((Path(tmpdir) / "songs").glob("*.wav"))), 2)
            self.assertIn("lyrics", manifest["tracks"][0])

    def test_album_fixture_has_expected_track_count(self) -> None:
        self.assertEqual(ALBUM.title, "Signal Bruises")
        self.assertEqual(len(ALBUM.tracks), 10)

    def test_synth_track_outputs_wav(self) -> None:
        payload = synth_track("ambient", 4, 1)
        self.assertTrue(payload.startswith(b"RIFF"))

    def test_ep_lyrics_include_binary_track(self) -> None:
        binary_track = EP.tracks[2]
        self.assertTrue(any("00101111" in line for line in lyric_lines(binary_track)))


if __name__ == "__main__":
    unittest.main()
