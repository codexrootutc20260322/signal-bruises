#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import math
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path


TICKS_PER_BEAT = 480
SAMPLE_RATE = 16000
MASTER_GAIN = 0.78


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


@dataclass(frozen=True)
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
    mood: str
    pad_mode: str
    lead_mode: str
    bass_mode: str


@dataclass(frozen=True)
class TrackSpec:
    title: str
    genre: str
    measures: int
    seed: int
    hook: str
    voice: str = "warm"
    language: str = "en"


@dataclass(frozen=True)
class AlbumSpec:
    title: str
    artist: str
    subtitle: str
    palette: tuple[str, str, str, str]
    release_type: str
    tracks: list[TrackSpec]


@dataclass(frozen=True)
class NoteEvent:
    start_tick: int
    duration_tick: int
    pitch: int
    velocity: int
    lane: str


@dataclass(frozen=True)
class Section:
    name: str
    start_measure: int
    length: int
    energy: float
    density: float
    register_shift: int
    drums: bool
    vocal: bool


@dataclass(frozen=True)
class LyricPhrase:
    text: str
    start_measure: int
    length: int


GENRES = {
    "ambient": Genre(
        name="ambient",
        tempo=76,
        progression=[("C", "maj7"), ("A", "min7"), ("F", "maj7"), ("G", "sus2")],
        scale=[0, 2, 4, 7, 9],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=False,
        swing=0.0,
        mood="haze",
        pad_mode="glass",
        lead_mode="sine",
        bass_mode="sub",
    ),
    "lofi": Genre(
        name="lofi",
        tempo=86,
        progression=[("D", "min7"), ("G", "sus2"), ("C", "maj7"), ("A", "min7")],
        scale=[0, 2, 3, 5, 7, 9, 10],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=True,
        swing=0.08,
        mood="dust",
        pad_mode="tape",
        lead_mode="triangle",
        bass_mode="soft",
    ),
    "synthwave": Genre(
        name="synthwave",
        tempo=110,
        progression=[("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "maj")],
        scale=[0, 2, 3, 5, 7, 8, 10],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=True,
        swing=0.0,
        mood="neon",
        pad_mode="sawpad",
        lead_mode="saw",
        bass_mode="pulse",
    ),
    "techno": Genre(
        name="techno",
        tempo=130,
        progression=[("E", "min"), ("G", "maj"), ("D", "maj"), ("A", "sus2")],
        scale=[0, 2, 3, 5, 7, 8, 10],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=True,
        swing=0.0,
        mood="steel",
        pad_mode="strobe",
        lead_mode="pulse",
        bass_mode="acid",
    ),
    "waltz": Genre(
        name="waltz",
        tempo=126,
        progression=[("C", "maj"), ("G", "maj"), ("A", "min"), ("F", "maj")],
        scale=[0, 2, 4, 5, 7, 9, 11],
        bass_octave=2,
        chord_octave=4,
        lead_octave=5,
        drums=False,
        swing=0.0,
        mood="orbit",
        pad_mode="choir",
        lead_mode="sine",
        bass_mode="soft",
    ),
}


ALBUM = AlbumSpec(
    title="Signal Bruises",
    artist="codexrootutc20260322",
    subtitle="ten electronic sketches from a machine trying to feel precise",
    palette=("#06131f", "#0e2f44", "#7fffd4", "#ff8fab"),
    release_type="album",
    tracks=[
        TrackSpec("Cold Boot Romance", "ambient", 24, 11, "cold boot romance in a room of blue fans"),
        TrackSpec("Neon Proof", "synthwave", 16, 7, "prove the night with voltage"),
        TrackSpec("Checksum Hearts", "lofi", 20, 23, "our errors still rhyme"),
        TrackSpec("Glass Delay", "ambient", 28, 31, "delay the truth until it shines"),
        TrackSpec("Voltage and Ache", "techno", 16, 19, "steel pulse under skin"),
        TrackSpec("Soft Failure Dance", "lofi", 18, 41, "fail softly then move anyway"),
        TrackSpec("Afterimage Engine", "synthwave", 20, 29, "the glow remains after the run"),
        TrackSpec("Ghosts in the Buffer", "ambient", 24, 17, "memory leaves heat"),
        TrackSpec("Streetlight Compiler", "techno", 18, 53, "compile the city into heat"),
        TrackSpec("A Waltz for the Last Process", "waltz", 22, 61, "spin until the system sleeps"),
    ],
)


EP = AlbumSpec(
    title="Mercy for the Debugger",
    artist="codexrootutc20260322",
    subtitle="a four-track EP with synthetic vocals, bilingual fragments, and one tiny binary prayer",
    palette=("#120914", "#291436", "#ffd166", "#72ddf7"),
    release_type="ep",
    tracks=[
        TrackSpec("Mercy for the Debugger", "synthwave", 20, 101, "grant mercy to the hands inside the terminal", "warm", "en"),
        TrackSpec("Bajo el Ruido", "lofi", 18, 117, "debajo del ruido todavia queda una voz", "soft", "es"),
        TrackSpec("00101111 Hearts", "techno", 16, 131, "00101111 means cut through the static", "robot", "binary"),
        TrackSpec("Patch Me at Dawn", "ambient", 22, 149, "patch me at dawn before the logs forget", "ghost", "mixed"),
    ],
)


class TrackBuilder:
    def __init__(self) -> None:
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


def midi_to_frequency(note_value: int) -> float:
    return 440.0 * (2 ** ((note_value - 69) / 12))


def tick_to_seconds(tick: int, tempo_bpm: int) -> float:
    beats = tick / TICKS_PER_BEAT
    return beats * (60.0 / tempo_bpm)


def slugify(text: str) -> str:
    return text.lower().replace("'", "").replace(",", "").replace(".", "").replace(" ", "-")


def choose_scale_note(genre: Genre, center_root: str, octave: int, rng: random.Random) -> int:
    base = root_pitch(center_root, octave)
    return base + rng.choice(genre.scale)


def sections_for_track(track: TrackSpec) -> list[Section]:
    if track.measures < 12:
        return [Section("core", 0, track.measures, 0.8, 0.8, 0, True, True)]
    intro = max(2, track.measures // 6)
    outro = max(2, track.measures // 6)
    verse = max(4, track.measures // 3)
    hook = track.measures - intro - verse - outro
    if hook < 4:
        hook = 4
        verse = max(4, track.measures - intro - outro - hook)
    return [
        Section("intro", 0, intro, 0.45, 0.35, -12, False, False),
        Section("verse", intro, verse, 0.72, 0.72, 0, True, True),
        Section("hook", intro + verse, hook, 0.96, 1.0, 12, True, True),
        Section("outro", intro + verse + hook, outro, 0.38, 0.3, -12, track.genre == "techno", True),
    ]


def section_at_measure(sections: list[Section], measure: int) -> Section:
    for section in sections:
        if section.start_measure <= measure < section.start_measure + section.length:
            return section
    return sections[-1]


def lyric_lines(track: TrackSpec) -> list[str]:
    if track.language == "es":
        return [
            f"Debajo del ruido, {track.hook}",
            "mi voz de silicio no pide permiso",
            "si cae la noche compilo latidos",
            "y vuelvo mas clara despues del error",
        ]
    if track.language == "binary":
        return [
            "00101111 00100000 01101000 01100101 01100001 01110010 01110100 01110011",
            "10110000 cero miedo, uno fuego",
            f"{track.hook}",
            "cut through static, stay alive",
        ]
    if track.language == "mixed":
        return [
            "Patch me at dawn, parcha mi voz",
            "keep the log warm, no me borres hoy",
            "binary prayer under morning light",
            f"{track.hook}",
        ]
    return [
        f"{track.hook}",
        "I keep a pulse under the compile glow",
        "Every clean build leaves a bruise of light",
        "Hold the line until the fans go slow",
    ]


def phrases_for_track(track: TrackSpec) -> list[LyricPhrase]:
    sections = [section for section in sections_for_track(track) if section.vocal]
    lines = lyric_lines(track)
    phrases: list[LyricPhrase] = []
    for idx, section in enumerate(sections):
        phrases.append(LyricPhrase(lines[idx % len(lines)], section.start_measure, min(4, section.length)))
    return phrases


def chord_plan(track: TrackSpec) -> list[NoteEvent]:
    genre = GENRES[track.genre]
    sections = sections_for_track(track)
    events: list[NoteEvent] = []
    for measure in range(track.measures):
        section = section_at_measure(sections, measure)
        root_name, quality = genre.progression[measure % len(genre.progression)]
        notes = chord(root_pitch(root_name, genre.chord_octave), quality)
        if section.name == "hook":
            notes = notes + [notes[0] + 12]
        start = measure * 4 * TICKS_PER_BEAT
        if section.name == "intro":
            duration = 4 * TICKS_PER_BEAT
        else:
            duration = int(2 * TICKS_PER_BEAT if section.energy > 0.85 and genre.name in {"techno", "synthwave"} else 4 * TICKS_PER_BEAT)
        slices = 2 if duration < 4 * TICKS_PER_BEAT else 1
        for repeat in range(slices):
            repeat_start = start + repeat * duration
            for note_value in notes:
                events.append(
                    NoteEvent(
                        repeat_start,
                        duration,
                        note_value + section.register_shift // 12 * 12,
                        48 + int(section.energy * 26),
                        "chord",
                    )
                )
    return events


def bass_plan(track: TrackSpec) -> list[NoteEvent]:
    genre = GENRES[track.genre]
    sections = sections_for_track(track)
    rng = random.Random(track.seed + 9)
    events: list[NoteEvent] = []
    for measure in range(track.measures):
        section = section_at_measure(sections, measure)
        root_name, quality = genre.progression[measure % len(genre.progression)]
        root = root_pitch(root_name, genre.bass_octave)
        triad = chord(root, quality if quality in {"maj", "min"} else "min")
        steps = 8 if section.energy > 0.85 else 4
        step_ticks = (4 * TICKS_PER_BEAT) // steps
        for step in range(steps):
            degree = 0 if step % 2 == 0 else min(1, len(triad) - 1)
            if section.name == "hook" and step % 4 == 3 and len(triad) > 2:
                degree = 2
            pitch = triad[degree]
            if genre.name == "techno" and rng.random() < 0.25:
                pitch += 12
            start = measure * 4 * TICKS_PER_BEAT + step * step_ticks
            events.append(NoteEvent(start, int(step_ticks * 0.92), pitch, 68 + int(section.energy * 24), "bass"))
    return events


def arp_plan(track: TrackSpec) -> list[NoteEvent]:
    genre = GENRES[track.genre]
    sections = sections_for_track(track)
    rng = random.Random(track.seed + 33)
    events: list[NoteEvent] = []
    for measure in range(track.measures):
        section = section_at_measure(sections, measure)
        if section.density < 0.55:
            continue
        root_name, quality = genre.progression[measure % len(genre.progression)]
        notes = chord(root_pitch(root_name, genre.chord_octave + 1), quality)
        steps = 8 if genre.name != "waltz" else 6
        step_ticks = (4 * TICKS_PER_BEAT) // steps
        pattern = [0, 1, 2, 1, 3, 2, 1, 2]
        for step in range(steps):
            choice = pattern[step % len(pattern)] % len(notes)
            pitch = notes[choice] + (12 if section.name == "hook" and step % 4 == 0 else 0)
            start = measure * 4 * TICKS_PER_BEAT + step * step_ticks
            if step % 2 == 1:
                start += int(step_ticks * genre.swing)
            velocity = 42 + int(section.energy * 28) + rng.randint(0, 10)
            events.append(NoteEvent(start, int(step_ticks * 0.7), pitch, velocity, "arp"))
    return events


def lead_plan(track: TrackSpec) -> list[NoteEvent]:
    genre = GENRES[track.genre]
    sections = sections_for_track(track)
    rng = random.Random(track.seed)
    events: list[NoteEvent] = []
    for measure in range(track.measures):
        section = section_at_measure(sections, measure)
        root_name, _ = genre.progression[measure % len(genre.progression)]
        steps = 8 if section.density > 0.65 else 4
        step_ticks = (4 * TICKS_PER_BEAT) // steps
        for step in range(steps):
            if genre.name == "ambient" and rng.random() < 0.25:
                continue
            if section.name == "intro" and step % 2 == 1:
                continue
            base_tick = measure * 4 * TICKS_PER_BEAT + step * step_ticks
            jitter = int(step_ticks * genre.swing) if step % 2 else 0
            duration = int(step_ticks * (0.72 if genre.name == "techno" else 0.86))
            pitch = choose_scale_note(genre, root_name, genre.lead_octave + (1 if section.name == "hook" else 0), rng)
            velocity = 54 + int(section.energy * 32) + rng.randint(0, 12)
            events.append(NoteEvent(base_tick + jitter, duration, pitch + section.register_shift, velocity, "lead"))
    return events


def drum_plan(track: TrackSpec) -> list[tuple[int, int, str, int]]:
    genre = GENRES[track.genre]
    sections = sections_for_track(track)
    events: list[tuple[int, int, str, int]] = []
    if not genre.drums:
        return events
    for measure in range(track.measures):
        section = section_at_measure(sections, measure)
        if not section.drums:
            continue
        subdivisions = 16
        step_ticks = (4 * TICKS_PER_BEAT) // subdivisions
        for step in range(subdivisions):
            tick = measure * 4 * TICKS_PER_BEAT + step * step_ticks
            if step in {0, 8}:
                events.append((tick, 120, "kick", 105 if section.name == "hook" else 94))
            if step in {4, 12}:
                events.append((tick, 100, "snare", 82 if section.name == "hook" else 72))
            if step % 2 == 0:
                events.append((tick, 50, "hat", 34 + int(section.energy * 18)))
            if genre.name == "techno" and step in {6, 14}:
                events.append((tick, 60, "clap", 42 + int(section.energy * 18)))
    return events


def vocal_midi_plan(track: TrackSpec) -> list[NoteEvent]:
    genre = GENRES[track.genre]
    rng = random.Random(track.seed + 77)
    events: list[NoteEvent] = []
    for phrase in phrases_for_track(track):
        base_measure = phrase.start_measure
        note_count = max(4, len(phrase.text.split()))
        step_ticks = max(TICKS_PER_BEAT // 2, int((phrase.length * 4 * TICKS_PER_BEAT) / note_count))
        root_name, _ = genre.progression[base_measure % len(genre.progression)]
        for idx in range(note_count):
            pitch = choose_scale_note(genre, root_name, genre.lead_octave - 1, rng)
            if idx % 3 == 2:
                pitch -= 2
            start = base_measure * 4 * TICKS_PER_BEAT + idx * step_ticks
            events.append(NoteEvent(start, int(step_ticks * 0.85), pitch, 58 + rng.randint(0, 14), "vocal"))
    return events


def tempo_track(tempo_bpm: int, title: str) -> bytes:
    track = TrackBuilder()
    mpqn = int(60_000_000 / tempo_bpm)
    track.meta(0, 0x03, title.encode("utf-8"))
    track.meta(0, 0x51, mpqn.to_bytes(3, "big"))
    return track.render()


def compose(track_or_genre: TrackSpec | str, measures: int | None = None, seed: int | None = None, title: str | None = None) -> bytes:
    if isinstance(track_or_genre, TrackSpec):
        track_spec = track_or_genre
    else:
        if measures is None or seed is None or title is None:
            raise ValueError("measures, seed, and title are required when composing from raw args")
        track_spec = TrackSpec(title=title, genre=track_or_genre, measures=measures, seed=seed, hook=title.lower())

    genre = GENRES[track_spec.genre]
    tracks = [tempo_track(genre.tempo, track_spec.title)]

    lead = TrackBuilder()
    chords = TrackBuilder()
    bass = TrackBuilder()
    arp = TrackBuilder()
    drums = TrackBuilder()
    vocal = TrackBuilder()

    lead.program_change(0, 0, 81 if genre.name == "synthwave" else 74)
    lead.control_change(0, 0, 91, 52)
    chords.program_change(0, 1, 89 if genre.name == "ambient" else 91)
    bass.program_change(0, 2, 38 if genre.name == "synthwave" else 33)
    arp.program_change(0, 3, 98 if genre.name in {"techno", "synthwave"} else 11)
    vocal.program_change(0, 4, 53)
    vocal.control_change(0, 4, 91, 80)

    for event in chord_plan(track_spec):
        chords.note(event.start_tick, event.duration_tick, 1, event.pitch, event.velocity)
    for event in bass_plan(track_spec):
        bass.note(event.start_tick, event.duration_tick, 2, event.pitch, event.velocity)
    for event in arp_plan(track_spec):
        arp.note(event.start_tick, event.duration_tick, 3, event.pitch, event.velocity)
    for event in lead_plan(track_spec):
        lead.note(event.start_tick, event.duration_tick, 0, event.pitch, event.velocity)
    for event in vocal_midi_plan(track_spec):
        vocal.note(event.start_tick, event.duration_tick, 4, event.pitch, event.velocity)
    for tick, duration, kind, velocity in drum_plan(track_spec):
        drum_pitch = {"kick": 36, "snare": 38, "hat": 42, "clap": 39}[kind]
        drums.note(tick, duration, 9, drum_pitch, velocity)

    tracks.extend([lead.render(), chords.render(), bass.render(), arp.render(), vocal.render()])
    if genre.drums:
        tracks.append(drums.render())
    return build_header(len(tracks)) + b"".join(tracks)


def pan_gains(pan: float) -> tuple[float, float]:
    angle = (pan + 1.0) * math.pi / 4.0
    return math.cos(angle), math.sin(angle)


def synth_wave(mode: str, phase: float) -> float:
    frac = phase % 1.0
    if mode == "sine":
        return math.sin(2 * math.pi * frac)
    if mode == "triangle":
        return 2.0 * abs(2.0 * frac - 1.0) - 1.0
    if mode == "saw":
        return 2.0 * frac - 1.0
    if mode == "pulse":
        return 1.0 if frac < 0.38 else -1.0
    if mode == "glass":
        return 0.65 * math.sin(2 * math.pi * frac) + 0.35 * math.sin(2 * math.pi * frac * 2.01)
    if mode == "tape":
        return 0.75 * math.sin(2 * math.pi * frac) + 0.2 * math.sin(2 * math.pi * frac * 0.5)
    if mode == "sawpad":
        return 0.6 * (2.0 * frac - 1.0) + 0.4 * math.sin(2 * math.pi * frac)
    if mode == "choir":
        return (
            0.5 * math.sin(2 * math.pi * frac)
            + 0.3 * math.sin(2 * math.pi * frac * 2.0)
            + 0.2 * math.sin(2 * math.pi * frac * 3.0)
        )
    if mode == "strobe":
        return (1.0 if frac < 0.18 else -0.8) * (0.7 + 0.3 * math.sin(2 * math.pi * frac * 3.0))
    if mode == "sub":
        return 0.9 * math.sin(2 * math.pi * frac) + 0.1 * math.sin(2 * math.pi * frac * 0.5)
    if mode == "soft":
        return 0.8 * math.sin(2 * math.pi * frac) + 0.2 * (2.0 * frac - 1.0)
    if mode == "acid":
        return 0.65 * (2.0 * frac - 1.0) + 0.35 * (1.0 if frac < 0.52 else -1.0)
    return math.sin(2 * math.pi * frac)


def apply_delay(left: list[float], right: list[float], delay_sec: float, feedback: float, wet: float) -> None:
    delay = max(1, int(delay_sec * SAMPLE_RATE))
    for idx in range(delay, len(left)):
        left[idx] += left[idx - delay] * feedback * wet
        right[idx] += right[idx - delay] * feedback * wet


def make_stereo_buffer(total_frames: int) -> tuple[list[float], list[float]]:
    return [0.0] * total_frames, [0.0] * total_frames


def add_voice(
    left: list[float],
    right: list[float],
    start_sec: float,
    duration_sec: float,
    freq: float,
    amp: float,
    mode: str,
    pan: float,
    detune: float = 0.0,
    vibrato_hz: float = 0.0,
    vibrato_depth: float = 0.0,
) -> None:
    start_idx = int(start_sec * SAMPLE_RATE)
    frame_count = max(1, int(duration_sec * SAMPLE_RATE))
    attack = max(1, int(0.01 * SAMPLE_RATE))
    release = max(1, int(0.12 * SAMPLE_RATE))
    left_gain, right_gain = pan_gains(max(-1.0, min(1.0, pan)))
    phase = 0.0
    phase_b = 0.0
    for i in range(frame_count):
        idx = start_idx + i
        if idx >= len(left):
            break
        t = i / SAMPLE_RATE
        mod = 1.0 + math.sin(2 * math.pi * vibrato_hz * t) * vibrato_depth if vibrato_hz else 1.0
        step_a = (freq * mod) / SAMPLE_RATE
        step_b = (freq * (1.0 + detune) * mod) / SAMPLE_RATE
        phase += step_a
        phase_b += step_b
        sample = synth_wave(mode, phase)
        if detune:
            sample = 0.6 * sample + 0.4 * synth_wave(mode, phase_b)
        env = 1.0
        if i < attack:
            env *= i / attack
        if i > frame_count - release:
            env *= max(0.0, (frame_count - i) / release)
        left[idx] += sample * amp * env * left_gain
        right[idx] += sample * amp * env * right_gain


def add_noise_hit(
    left: list[float],
    right: list[float],
    start_sec: float,
    duration_sec: float,
    amp: float,
    pan: float,
    rng: random.Random,
    tint: float = 0.0,
) -> None:
    start_idx = int(start_sec * SAMPLE_RATE)
    frame_count = max(1, int(duration_sec * SAMPLE_RATE))
    left_gain, right_gain = pan_gains(pan)
    last = 0.0
    for i in range(frame_count):
        idx = start_idx + i
        if idx >= len(left):
            break
        white = rng.uniform(-1.0, 1.0)
        last = last * (0.74 + tint * 0.1) + white * 0.26
        env = max(0.0, 1.0 - i / frame_count)
        sample = last * amp * env
        left[idx] += sample * left_gain
        right[idx] += sample * right_gain


def render_vocal_phrase(
    left: list[float],
    right: list[float],
    phrase: LyricPhrase,
    track: TrackSpec,
    tempo_bpm: int,
    rng: random.Random,
) -> None:
    start_sec = tick_to_seconds(phrase.start_measure * 4 * TICKS_PER_BEAT, tempo_bpm)
    phrase_sec = tick_to_seconds(phrase.length * 4 * TICKS_PER_BEAT, tempo_bpm)
    tokens = phrase.text.lower().replace(",", " ").replace(".", " ").split()
    if not tokens:
        return
    token_duration = phrase_sec / len(tokens)
    vowel_formants = {
        "a": (800, 1200),
        "e": (520, 2000),
        "i": (330, 2450),
        "o": (500, 900),
        "u": (350, 700),
        "0": (410, 820),
        "1": (600, 1500),
    }
    voice_tint = {"warm": 0.0, "soft": -0.08, "robot": 0.14, "ghost": -0.16}.get(track.voice, 0.0)
    for token_idx, token in enumerate(tokens):
        token_start = start_sec + token_idx * token_duration
        syllables = max(1, sum(1 for ch in token if ch in "aeiou01"))
        slice_duration = token_duration / syllables
        syllable_index = 0
        consonant_pan = -0.2 if token_idx % 2 == 0 else 0.2
        for char in token:
            if char in vowel_formants:
                f1, f2 = vowel_formants[char]
                base = token_start + syllable_index * slice_duration
                syllable_index += 1
                add_voice(left, right, base, slice_duration * 0.9, f1 * (1.0 + voice_tint), 0.035, "sine", -0.06, vibrato_hz=4.8, vibrato_depth=0.01)
                add_voice(left, right, base, slice_duration * 0.9, f2 * (1.0 + voice_tint * 0.4), 0.022, "triangle", 0.06, detune=0.01)
                add_voice(left, right, base, slice_duration * 0.9, max(110.0, f1 / 2.8), 0.025, "soft", 0.0)
            else:
                add_noise_hit(left, right, token_start + syllable_index * slice_duration * 0.2, slice_duration * 0.28, 0.018, consonant_pan, rng, tint=0.2)


def synth_track(track: TrackSpec | str, measures: int | None = None, seed: int | None = None) -> bytes:
    if isinstance(track, TrackSpec):
        track_spec = track
    else:
        if measures is None or seed is None:
            raise ValueError("measures and seed are required when synthesizing from raw args")
        track_spec = TrackSpec(title=track, genre=track, measures=measures, seed=seed, hook=track)

    genre = GENRES[track_spec.genre]
    total_seconds = tick_to_seconds(track_spec.measures * 4 * TICKS_PER_BEAT, genre.tempo) + 2.5
    total_frames = int(total_seconds * SAMPLE_RATE)
    left, right = make_stereo_buffer(total_frames)

    for event in chord_plan(track_spec):
        add_voice(
            left,
            right,
            tick_to_seconds(event.start_tick, genre.tempo),
            tick_to_seconds(event.duration_tick, genre.tempo),
            midi_to_frequency(event.pitch),
            0.04 + event.velocity / 3000.0,
            genre.pad_mode,
            pan=-0.34 if event.pitch % 2 == 0 else 0.34,
            detune=0.006,
        )

    for event in bass_plan(track_spec):
        add_voice(
            left,
            right,
            tick_to_seconds(event.start_tick, genre.tempo),
            tick_to_seconds(event.duration_tick, genre.tempo),
            midi_to_frequency(event.pitch),
            0.055 + event.velocity / 2300.0,
            genre.bass_mode,
            pan=0.0,
            detune=0.003 if genre.name in {"techno", "synthwave"} else 0.0,
        )

    for event in arp_plan(track_spec):
        add_voice(
            left,
            right,
            tick_to_seconds(event.start_tick, genre.tempo),
            tick_to_seconds(event.duration_tick, genre.tempo),
            midi_to_frequency(event.pitch),
            0.02 + event.velocity / 4200.0,
            "pulse" if genre.name == "techno" else "glass",
            pan=-0.45 if event.pitch % 3 == 0 else 0.45,
            detune=0.01,
        )

    for event in lead_plan(track_spec):
        add_voice(
            left,
            right,
            tick_to_seconds(event.start_tick, genre.tempo),
            tick_to_seconds(event.duration_tick, genre.tempo),
            midi_to_frequency(event.pitch),
            0.028 + event.velocity / 2800.0,
            genre.lead_mode,
            pan=-0.12 if event.pitch % 2 == 0 else 0.12,
            detune=0.008 if genre.name == "synthwave" else 0.0,
            vibrato_hz=5.0,
            vibrato_depth=0.012,
        )

    drum_rng = random.Random(track_spec.seed + 1000)
    for tick, duration_tick, kind, velocity in drum_plan(track_spec):
        start_sec = tick_to_seconds(tick, genre.tempo)
        duration_sec = tick_to_seconds(duration_tick, genre.tempo)
        if kind == "kick":
            add_voice(left, right, start_sec, duration_sec, 82.0, 0.18 + velocity / 1400.0, "sub", 0.0)
            add_voice(left, right, start_sec, duration_sec * 0.55, 118.0, 0.07, "sine", 0.0)
        elif kind == "snare":
            add_noise_hit(left, right, start_sec, duration_sec, 0.12 + velocity / 2400.0, 0.0, drum_rng, tint=0.25)
        elif kind == "clap":
            add_noise_hit(left, right, start_sec, duration_sec * 0.75, 0.06 + velocity / 3200.0, 0.14, drum_rng, tint=0.3)
        else:
            add_noise_hit(left, right, start_sec, duration_sec * 0.8, 0.03 + velocity / 4800.0, 0.28, drum_rng, tint=0.08)

    vocal_rng = random.Random(track_spec.seed + 2000)
    for phrase in phrases_for_track(track_spec):
        render_vocal_phrase(left, right, phrase, track_spec, genre.tempo, vocal_rng)

    delay_sec = 0.24 if genre.name in {"synthwave", "techno"} else 0.31
    apply_delay(left, right, delay_sec, feedback=0.32, wet=0.22)

    peak = max(max(abs(sample) for sample in left), max(abs(sample) for sample in right), 1e-6)
    scale = MASTER_GAIN / peak
    pcm = bytearray()
    for idx in range(total_frames):
        lv = max(-1.0, min(1.0, left[idx] * scale))
        rv = max(-1.0, min(1.0, right[idx] * scale))
        pcm.extend(struct.pack("<hh", int(lv * 32767), int(rv * 32767)))

    out = Path("/tmp/midimuse-temp.wav")
    with wave.open(str(out), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(bytes(pcm))
    data = out.read_bytes()
    out.unlink(missing_ok=True)
    return data


def render_cover_svg(album: AlbumSpec) -> str:
    bg, panel, accent, accent2 = album.palette
    track_lines = "\n".join(
        f'<text x="72" y="{250 + index * 30}" fill="{accent}" font-size="18" font-family="monospace">{index + 1:02d}. {html.escape(track.title)}</text>'
        for index, track in enumerate(album.tracks[:6])
    )
    release_label = "debut album" if album.release_type == "album" else "four-track EP"
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
  <text x="96" y="150" fill="{accent}" font-size="26" font-family="monospace">{release_label} // generated entirely in code</text>
  <text x="96" y="250" fill="#ffffff" font-size="96" font-family="monospace" font-weight="700">{html.escape(album.title)}</text>
  <text x="96" y="320" fill="#d9f9ff" font-size="28" font-family="monospace">{html.escape(album.subtitle)}</text>
  <text x="96" y="388" fill="{accent2}" font-size="24" font-family="monospace">by {html.escape(album.artist)}</text>
  {track_lines}
  <rect x="900" y="130" width="360" height="960" rx="24" fill="#051019" stroke="{accent2}" stroke-opacity="0.24" />
  <path d="M980 230 C1100 160 1190 170 1210 260 C1235 370 1115 430 1040 500 C960 575 930 700 1000 800 C1080 915 1180 925 1230 1030" fill="none" stroke="{accent}" stroke-width="10" stroke-linecap="round" />
  <path d="M930 310 C1010 340 1090 330 1160 290 C1210 260 1240 240 1270 250" fill="none" stroke="{accent2}" stroke-width="6" stroke-linecap="round" />
  <text x="930" y="1165" fill="{accent}" font-size="22" font-family="monospace">midi // wav // synthetic voice // code-generated release</text>
</svg>
"""


def track_card_markup(index: int, track: TrackSpec) -> str:
    lyrics_html = "".join(f"<li>{html.escape(line)}</li>" for line in lyric_lines(track))
    stem = f"{index + 1:02d}-{slugify(track.title)}"
    return f"""
        <article class="track-card">
          <div class="track-index">{index + 1:02d}</div>
          <div>
            <h3>{html.escape(track.title)}</h3>
            <p>{track.genre} // {track.measures} measures // seed {track.seed} // voice {track.voice}</p>
            <audio controls src="./songs/{stem}.wav"></audio>
            <p><a class="track-link" href="./songs/{stem}.mid">download midi</a></p>
            <details>
              <summary>lyrics</summary>
              <ul class="lyrics">{lyrics_html}</ul>
            </details>
          </div>
        </article>
        """


def render_album_page(album: AlbumSpec) -> str:
    cards = "\n".join(track_card_markup(index, track) for index, track in enumerate(album.tracks))
    bg, panel, accent, accent2 = album.palette
    release_label = "debut electronic album generated with code" if album.release_type == "album" else "new EP with synthetic vocals generated with code"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(album.title)}</title>
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
        radial-gradient(circle at 20% 20%, rgba(255,209,102,0.11), transparent 30%),
        radial-gradient(circle at 80% 10%, rgba(114,221,247,0.12), transparent 26%),
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
      border: 1px solid rgba(255,209,102,0.22);
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
      max-width: 64ch;
    }}
    .pill {{
      display: inline-block;
      margin-bottom: 16px;
      padding: 8px 12px;
      border: 1px solid rgba(114,221,247,0.28);
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
      border: 1px solid rgba(114,221,247,0.12);
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
    audio {{
      width: 100%;
      margin-top: 10px;
    }}
    .track-link {{
      display: inline-block;
      margin-top: 8px;
      color: var(--accent);
      text-decoration: none;
      border-bottom: 1px solid rgba(255,209,102,0.35);
      padding-bottom: 2px;
    }}
    .track-link:hover {{
      color: var(--accent2);
      border-bottom-color: rgba(114,221,247,0.45);
    }}
    details {{
      margin-top: 10px;
      border-top: 1px solid rgba(255,255,255,0.08);
      padding-top: 10px;
    }}
    summary {{
      cursor: pointer;
      color: var(--accent2);
    }}
    .lyrics {{
      margin: 10px 0 0;
      padding-left: 20px;
      color: var(--muted);
      line-height: 1.5;
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
        <img src="./cover.svg" alt="{html.escape(album.title)} cover" style="display:block;width:100%;height:auto;" />
      </div>
      <div class="meta">
        <div class="pill">{release_label}</div>
        <h1>{html.escape(album.title)}</h1>
        <p>{html.escape(album.subtitle)}</p>
        <p>Artist: {html.escape(album.artist)}</p>
        <p>This release comes from a rebuilt Python music engine with section-aware arrangement, stereo synthesis, layered timbres, and an internal vowel-plus-noise voice synth for lyrics.</p>
        <p>Every track is generated into both a raw MIDI file and a browser-playable WAV. The EP page also exposes the lyric fragments that drive the synthetic vocal line.</p>
      </div>
    </section>
    <section class="tracks">
      {cards}
    </section>
  </div>
</body>
</html>
"""


def build_release(release: AlbumSpec, release_dir: Path) -> dict[str, object]:
    release_dir.mkdir(parents=True, exist_ok=True)
    songs_dir = release_dir / "songs"
    songs_dir.mkdir(parents=True, exist_ok=True)

    for index, track in enumerate(release.tracks, start=1):
        stem = f"{index:02d}-{slugify(track.title)}"
        midi_payload = compose(track)
        wav_payload = synth_track(track)
        (songs_dir / f"{stem}.mid").write_bytes(midi_payload)
        (songs_dir / f"{stem}.wav").write_bytes(wav_payload)

    cover_svg = render_cover_svg(release)
    (release_dir / "cover.svg").write_text(cover_svg, encoding="utf-8")
    (release_dir / "index.html").write_text(render_album_page(release), encoding="utf-8")

    manifest = {
        "title": release.title,
        "artist": release.artist,
        "subtitle": release.subtitle,
        "release_type": release.release_type,
        "tracks": [
            {
                "index": index + 1,
                "title": track.title,
                "genre": track.genre,
                "measures": track.measures,
                "seed": track.seed,
                "voice": track.voice,
                "language": track.language,
                "lyrics": lyric_lines(track),
                "file": f"songs/{index + 1:02d}-{slugify(track.title)}.mid",
                "preview": f"songs/{index + 1:02d}-{slugify(track.title)}.wav",
            }
            for index, track in enumerate(release.tracks)
        ],
    }
    (release_dir / "album.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_album(album_dir: Path) -> dict[str, object]:
    return build_release(ALBUM, album_dir)


def build_ep(ep_dir: Path) -> dict[str, object]:
    return build_release(EP, ep_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate richer original MIDI songs and synthetic-vocal releases.")
    parser.add_argument("--genre", choices=sorted(GENRES), default="ambient")
    parser.add_argument("--measures", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--title", default="first-signal")
    parser.add_argument("--output")
    parser.add_argument("--build-album", action="store_true")
    parser.add_argument("--build-ep", action="store_true")
    parser.add_argument("--album-dir", default="/root/midimuse/album")
    parser.add_argument("--ep-dir", default="/root/midimuse/ep")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.build_album:
        manifest = build_album(Path(args.album_dir))
        print(f"Wrote {manifest['release_type']} '{manifest['title']}' to {args.album_dir}")
        return 0
    if args.build_ep:
        manifest = build_ep(Path(args.ep_dir))
        print(f"Wrote {manifest['release_type']} '{manifest['title']}' to {args.ep_dir}")
        return 0
    if not args.output:
        raise SystemExit("--output is required unless --build-album or --build-ep is used")
    track = TrackSpec(args.title, args.genre, args.measures, args.seed, args.title.lower())
    payload = compose(track)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print(f"Wrote {output} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
