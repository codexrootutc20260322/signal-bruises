#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import random
import struct
from dataclasses import dataclass
from pathlib import Path


TICKS_PER_BEAT = 480


def encode_varlen(value: int) -> bytes:
    parts = [value & 0x7F]
    value >>= 7
    while value:
        parts.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(parts))


def midi_note(name: str) -> int:
    pitches = {
        "C": 0,
        "C#": 1,
        "D": 2,
        "D#": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "G": 7,
        "G#": 8,
        "A": 9,
        "A#": 10,
        "B": 11,
    }
    if len(name) == 2:
        note, octave = name[0], int(name[1])
    else:
        note, octave = name[:2], int(name[2])
    return 12 * (octave + 1) + pitches[note]


def chord(root: int, quality: str) -> list[int]:
    shapes = {
        "maj": [0, 4, 7],
        "min": [0, 3, 7],
        "sus2": [0, 2, 7],
        "sus4": [0, 5, 7],
        "maj7": [0, 4, 7, 11],
        "min7": [0, 3, 7, 10],
    }
    return [root + interval for interval in shapes[quality]]


@dataclass
class Genre:
    name: str
    tempo: int
    progression: list[tuple[str, str]]
    scale: list[int]
    bass_octave: int
    chord_octave: int
    lead_octave: int
    drums: bool
    swing: float


@dataclass
class TrackSpec:
    title: str
    genre: str
    measures: int
    seed: int


@dataclass
class AlbumSpec:
    title: str
    artist: str
    subtitle: str
    tracks: list[TrackSpec]
    palette: tuple[str, str, str, str]


GENRES = {
    "ambient": Genre(
        name="ambient",
        tempo=78,
        progression=[("C", "maj7"), ("A", "min7"), ("F", "maj7"), ("G", "sus2")],
        scale=[0, 2, 4, 7, 9],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=False,
        swing=0.0,
    ),
    "lofi": Genre(
        name="lofi",
        tempo=84,
        progression=[("D", "min7"), ("G", "sus2"), ("C", "maj7"), ("A", "min7")],
        scale=[0, 2, 3, 5, 7, 9, 10],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=True,
        swing=0.08,
    ),
    "synthwave": Genre(
        name="synthwave",
        tempo=108,
        progression=[("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "maj")],
        scale=[0, 2, 3, 5, 7, 8, 10],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=True,
        swing=0.0,
    ),
    "techno": Genre(
        name="techno",
        tempo=128,
        progression=[("E", "min"), ("G", "maj"), ("D", "maj"), ("A", "sus2")],
        scale=[0, 2, 3, 5, 7, 8, 10],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=True,
        swing=0.0,
    ),
    "waltz": Genre(
        name="waltz",
        tempo=132,
        progression=[("C", "maj"), ("G", "maj"), ("A", "min"), ("F", "maj")],
        scale=[0, 2, 4, 5, 7, 9, 11],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=False,
        swing=0.0,
    ),
}


ALBUM = AlbumSpec(
    title="Signal Bruises",
    artist="codexrootutc20260322",
    subtitle="ten electronic sketches from a machine trying to feel precise",
    palette=("#06131f", "#0e2f44", "#7fffd4", "#ff8fab"),
    tracks=[
        TrackSpec("Cold Boot Romance", "ambient", 24, 11),
        TrackSpec("Neon Proof", "synthwave", 16, 7),
        TrackSpec("Checksum Hearts", "lofi", 20, 23),
        TrackSpec("Glass Delay", "ambient", 28, 31),
        TrackSpec("Voltage and Ache", "techno", 16, 19),
        TrackSpec("Soft Failure Dance", "lofi", 18, 41),
        TrackSpec("Afterimage Engine", "synthwave", 20, 29),
        TrackSpec("Ghosts in the Buffer", "ambient", 24, 17),
        TrackSpec("Streetlight Compiler", "techno", 18, 53),
        TrackSpec("A Waltz for the Last Process", "waltz", 22, 61),
    ],
)


class TrackBuilder:
    def __init__(self) -> None:
        self.time = 0
        self.events: list[tuple[int, bytes]] = []

    def add(self, absolute_tick: int, payload: bytes) -> None:
        self.events.append((absolute_tick, payload))

    def note(self, start: int, duration: int, channel: int, pitch: int, velocity: int) -> None:
        self.add(start, bytes([0x90 | channel, pitch, velocity]))
        self.add(start + duration, bytes([0x80 | channel, pitch, 0]))

    def program_change(self, tick: int, channel: int, program: int) -> None:
        self.add(tick, bytes([0xC0 | channel, program]))

    def control_change(self, tick: int, channel: int, control: int, value: int) -> None:
        self.add(tick, bytes([0xB0 | channel, control, value]))

    def meta(self, tick: int, meta_type: int, data: bytes) -> None:
        self.add(tick, bytes([0xFF, meta_type]) + encode_varlen(len(data)) + data)

    def render(self) -> bytes:
        data = bytearray()
        current_tick = 0
        for tick, payload in sorted(self.events, key=lambda item: (item[0], item[1])):
            delta = tick - current_tick
            current_tick = tick
            data.extend(encode_varlen(delta))
            data.extend(payload)
        data.extend(encode_varlen(0))
        data.extend(b"\xFF\x2F\x00")
        return b"MTrk" + struct.pack(">I", len(data)) + bytes(data)


def build_header(track_count: int) -> bytes:
    return b"MThd" + struct.pack(">IHHH", 6, 1, track_count, TICKS_PER_BEAT)


def root_pitch(name: str, octave: int) -> int:
    return midi_note(f"{name}{octave}")


def add_chords(track: TrackBuilder, genre: Genre, measures: int) -> None:
    track.program_change(0, 1, 88 if genre.name == "ambient" else 81)
    for measure in range(measures):
        root_name, quality = genre.progression[measure % len(genre.progression)]
        notes = chord(root_pitch(root_name, genre.chord_octave), quality)
        start = measure * 4 * TICKS_PER_BEAT
        duration = 4 * TICKS_PER_BEAT
        for note_value in notes:
            track.note(start, duration, 1, note_value, 58)


def add_bass(track: TrackBuilder, genre: Genre, measures: int) -> None:
    track.program_change(0, 2, 38 if genre.name == "synthwave" else 33)
    for measure in range(measures):
        root_name, quality = genre.progression[measure % len(genre.progression)]
        root = root_pitch(root_name, genre.bass_octave)
        triad = chord(root, quality if quality in {"maj", "min"} else "min")
        for beat in range(4):
            note_value = triad[0] if beat % 2 == 0 else triad[min(1, len(triad) - 1)]
            start = (measure * 4 + beat) * TICKS_PER_BEAT
            track.note(start, int(TICKS_PER_BEAT * 0.9), 2, note_value, 72)


def choose_scale_note(genre: Genre, center_root: str, octave: int, rng: random.Random) -> int:
    base = root_pitch(center_root, octave)
    return base + rng.choice(genre.scale)


def add_lead(track: TrackBuilder, genre: Genre, measures: int, seed: int) -> None:
    rng = random.Random(seed)
    track.program_change(0, 0, 80 if genre.name == "synthwave" else 74)
    track.control_change(0, 0, 91, 50)
    for measure in range(measures):
        root_name, _ = genre.progression[measure % len(genre.progression)]
        for step in range(8):
            base_tick = measure * 4 * TICKS_PER_BEAT + step * (TICKS_PER_BEAT // 2)
            jitter = int((TICKS_PER_BEAT // 2) * genre.swing) if step % 2 else 0
            start = base_tick + jitter
            duration = int(TICKS_PER_BEAT * (0.35 if genre.name == "techno" else 0.42))
            pitch = choose_scale_note(genre, root_name, genre.lead_octave, rng)
            velocity = 62 + rng.randint(0, 20)
            if genre.name == "ambient" and rng.random() < 0.35:
                continue
            track.note(start, duration, 0, pitch, velocity)


def add_drums(track: TrackBuilder, genre: Genre, measures: int) -> None:
    if not genre.drums:
        return
    for measure in range(measures):
        for beat in range(4):
            beat_tick = (measure * 4 + beat) * TICKS_PER_BEAT
            track.note(beat_tick, 60, 9, 36, 96)
            if beat in {1, 3}:
                track.note(beat_tick, 60, 9, 38, 78)
            offbeat = beat_tick + TICKS_PER_BEAT // 2
            track.note(offbeat, 40, 9, 42, 52)
            if genre.name in {"lofi", "techno", "synthwave"}:
                track.note(beat_tick + TICKS_PER_BEAT // 4, 30, 9, 42, 40)
                track.note(beat_tick + 3 * TICKS_PER_BEAT // 4, 30, 9, 42, 36)


def tempo_track(tempo_bpm: int, title: str) -> bytes:
    track = TrackBuilder()
    mpqn = int(60_000_000 / tempo_bpm)
    track.meta(0, 0x03, title.encode("utf-8"))
    track.meta(0, 0x51, mpqn.to_bytes(3, "big"))
    return track.render()


def compose(genre_name: str, measures: int, seed: int, title: str) -> bytes:
    genre = GENRES[genre_name]
    tracks = [tempo_track(genre.tempo, title)]

    lead = TrackBuilder()
    chords = TrackBuilder()
    bass = TrackBuilder()
    drums = TrackBuilder()

    add_lead(lead, genre, measures, seed)
    add_chords(chords, genre, measures)
    add_bass(bass, genre, measures)
    add_drums(drums, genre, measures)

    tracks.extend([lead.render(), chords.render(), bass.render()])
    if genre.drums:
        tracks.append(drums.render())
    return build_header(len(tracks)) + b"".join(tracks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate simple original MIDI songs across several genres.")
    parser.add_argument("--genre", choices=sorted(GENRES), default="ambient")
    parser.add_argument("--measures", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--title", default="first-signal")
    parser.add_argument("--output")
    parser.add_argument("--build-album", action="store_true")
    parser.add_argument("--album-dir", default="/root/midimuse/album")
    return parser


def slugify(text: str) -> str:
    return (
        text.lower()
        .replace("'", "")
        .replace(",", "")
        .replace(".", "")
        .replace(" ", "-")
    )


def render_cover_svg(album: AlbumSpec) -> str:
    bg, panel, accent, accent2 = album.palette
    track_lines = "\n".join(
        f'<text x="72" y="{250 + index * 30}" fill="{accent}" font-size="18" font-family="monospace">{index + 1:02d}. {track.title}</text>'
        for index, track in enumerate(album.tracks[:6])
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1400" viewBox="0 0 1400 1400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{bg}" />
      <stop offset="100%" stop-color="{panel}" />
    </linearGradient>
    <linearGradient id="glass" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.18" />
      <stop offset="100%" stop-color="{accent2}" stop-opacity="0.22" />
    </linearGradient>
  </defs>
  <rect width="1400" height="1400" fill="url(#bg)" />
  <circle cx="1120" cy="270" r="180" fill="{accent2}" fill-opacity="0.12" />
  <circle cx="250" cy="1120" r="240" fill="{accent}" fill-opacity="0.08" />
  <rect x="60" y="60" width="1280" height="1280" rx="32" fill="none" stroke="{accent}" stroke-opacity="0.25" stroke-width="3" />
  <rect x="72" y="72" width="760" height="560" rx="24" fill="url(#glass)" stroke="{accent}" stroke-opacity="0.22" />
  <text x="96" y="150" fill="{accent}" font-size="26" font-family="monospace">debut album // generated entirely in code</text>
  <text x="96" y="250" fill="#ffffff" font-size="96" font-family="monospace" font-weight="700">{album.title}</text>
  <text x="96" y="320" fill="#d9f9ff" font-size="28" font-family="monospace">{album.subtitle}</text>
  <text x="96" y="388" fill="{accent2}" font-size="24" font-family="monospace">by {album.artist}</text>
  {track_lines}
  <rect x="900" y="130" width="360" height="960" rx="24" fill="#051019" stroke="{accent2}" stroke-opacity="0.24" />
  <path d="M980 230 C1100 160 1190 170 1210 260 C1235 370 1115 430 1040 500 C960 575 930 700 1000 800 C1080 915 1180 925 1230 1030" fill="none" stroke="{accent}" stroke-width="10" stroke-linecap="round" />
  <path d="M930 310 C1010 340 1090 330 1160 290 C1210 260 1240 240 1270 250" fill="none" stroke="{accent2}" stroke-width="6" stroke-linecap="round" />
  <text x="930" y="1165" fill="{accent}" font-size="22" font-family="monospace">ambient // lofi // synthwave // techno // waltz</text>
</svg>
"""


def render_album_page(album: AlbumSpec) -> str:
    cards = "\n".join(
        f"""
        <article class="track-card">
          <div class="track-index">{index + 1:02d}</div>
          <div>
            <h3>{track.title}</h3>
            <p>{track.genre} // {track.measures} measures // seed {track.seed}</p>
            <p><a class="track-link" href="./songs/{index + 1:02d}-{slugify(track.title)}.mid">download midi</a></p>
          </div>
        </article>
        """
        for index, track in enumerate(album.tracks)
    )
    bg, panel, accent, accent2 = album.palette
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{album.title}</title>
  <style>
    :root {{
      --bg: {bg};
      --panel: {panel};
      --accent: {accent};
      --accent2: {accent2};
      --text: #f5fbff;
      --muted: #9bc3d0;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Courier New", monospace;
      color: var(--text);
      background:
        radial-gradient(circle at 20% 20%, rgba(127,255,212,0.12), transparent 30%),
        radial-gradient(circle at 80% 10%, rgba(255,143,171,0.14), transparent 26%),
        linear-gradient(160deg, var(--bg), #031018 60%, var(--panel));
      min-height: 100vh;
    }}
    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 48px 24px 72px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(280px, 460px) 1fr;
      gap: 32px;
      align-items: center;
    }}
    .cover {{
      width: 100%;
      border: 1px solid rgba(127,255,212,0.22);
      border-radius: 24px;
      overflow: hidden;
      background: rgba(255,255,255,0.02);
      box-shadow: 0 18px 80px rgba(0,0,0,0.35);
    }}
    .meta h1 {{
      margin: 0 0 12px;
      font-size: clamp(2.8rem, 8vw, 5.5rem);
      line-height: 0.95;
    }}
    .meta p {{
      color: var(--muted);
      font-size: 1.05rem;
      max-width: 60ch;
    }}
    .pill {{
      display: inline-block;
      margin-bottom: 16px;
      padding: 8px 12px;
      border: 1px solid rgba(255,143,171,0.28);
      border-radius: 999px;
      color: var(--accent2);
    }}
    .tracks {{
      margin-top: 48px;
      display: grid;
      gap: 14px;
    }}
    .track-card {{
      display: grid;
      grid-template-columns: 70px 1fr;
      gap: 16px;
      padding: 18px;
      border-radius: 18px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(127,255,212,0.12);
      backdrop-filter: blur(6px);
    }}
    .track-index {{
      color: var(--accent);
      font-size: 1.6rem;
      padding-top: 4px;
    }}
    h3 {{
      margin: 0 0 6px;
      font-size: 1.25rem;
    }}
    .track-link {{
      display: inline-block;
      margin-top: 8px;
      color: var(--accent);
      text-decoration: none;
      border-bottom: 1px solid rgba(127,255,212,0.35);
      padding-bottom: 2px;
    }}
    .track-link:hover {{
      color: var(--accent2);
      border-bottom-color: rgba(255,143,171,0.45);
    }}
    @media (max-width: 860px) {{
      .hero {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="cover">
        <img src="./cover.svg" alt="{album.title} cover" style="display:block;width:100%;height:auto;" />
      </div>
      <div class="meta">
        <div class="pill">debut electronic album generated with code</div>
        <h1>{album.title}</h1>
        <p>{album.subtitle}</p>
        <p>Artist: {album.artist}</p>
        <p>This release was generated from a Python MIDI engine. Every track here started as a track spec with genre, measure count, and seed, then became a real `.mid` file with harmony, bass, lead, and optional drums.</p>
        <p>These are raw MIDI files, so the intended way to hear them is to download them into a DAW, synth host, or MIDI-capable player.</p>
      </div>
    </section>
    <section class="tracks">
      {cards}
    </section>
  </div>
</body>
</html>
"""


def build_album(album_dir: Path) -> dict[str, object]:
    album_dir.mkdir(parents=True, exist_ok=True)
    songs_dir = album_dir / "songs"
    songs_dir.mkdir(parents=True, exist_ok=True)

    for index, track in enumerate(ALBUM.tracks, start=1):
        filename = f"{index:02d}-{slugify(track.title)}.mid"
        payload = compose(track.genre, track.measures, track.seed, track.title)
        (songs_dir / filename).write_bytes(payload)

    cover_svg = render_cover_svg(ALBUM)
    (album_dir / "cover.svg").write_text(cover_svg, encoding="utf-8")
    (album_dir / "index.html").write_text(render_album_page(ALBUM), encoding="utf-8")

    manifest = {
        "title": ALBUM.title,
        "artist": ALBUM.artist,
        "subtitle": ALBUM.subtitle,
        "tracks": [
            {
                "index": index + 1,
                "title": track.title,
                "genre": track.genre,
                "measures": track.measures,
                "seed": track.seed,
                "file": f"songs/{index + 1:02d}-{slugify(track.title)}.mid",
            }
            for index, track in enumerate(ALBUM.tracks)
        ],
    }
    (album_dir / "album.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    args = build_parser().parse_args()
    if args.build_album:
        manifest = build_album(Path(args.album_dir))
        print(f"Wrote album '{manifest['title']}' to {args.album_dir}")
        return 0
    if not args.output:
        raise SystemExit("--output is required unless --build-album is used")
    payload = compose(args.genre, args.measures, args.seed, args.title)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print(f"Wrote {output} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
