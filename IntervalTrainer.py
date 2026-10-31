"""Interval ear trainer.

Pick an interval with the number row (1-9, 0, -, =). The program keeps
playing that interval on random roots between C2 and C6: low note, high
note, both together, then high and low again. Space stops/resumes, Esc quits.
"""

import glob
import os
import random
import sys
from dataclasses import dataclass

import numpy as np
import pygame

SAMPLE_RATE = 44100
ROOT_LOW, ROOT_HIGH = 36, 84  # C2..C6 (middle C = 60, +/- 2 octaves)

INTERVALS = [
    (1, "1", "Minor 2nd", "m2"),
    (2, "2", "Major 2nd", "M2"),
    (3, "3", "Minor 3rd", "m3"),
    (4, "4", "Major 3rd", "M3"),
    (5, "5", "Perfect 4th", "P4"),
    (6, "6", "Tritone", "TT"),
    (7, "7", "Perfect 5th", "P5"),
    (8, "8", "Minor 6th", "m6"),
    (9, "9", "Major 6th", "M6"),
    (10, "0", "Minor 7th", "m7"),
    (11, "-", "Major 7th", "M7"),
    (12, "=", "Octave", "P8"),
]

KEY_TO_SEMITONES = {
    pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3, pygame.K_4: 4,
    pygame.K_5: 5, pygame.K_6: 6, pygame.K_7: 7, pygame.K_8: 8,
    pygame.K_9: 9, pygame.K_0: 10, pygame.K_MINUS: 11, pygame.K_EQUALS: 12,
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


@dataclass
class NoteEvent:
    start: float  # seconds
    duration: float  # seconds until note-off
    midi: int


# --------------------------------------------------------------------------
# Sound engines. Both render a list of NoteEvents to an int16 stereo buffer.
# --------------------------------------------------------------------------

def find_soundfont() -> str | None:
    """Look for a .sf2 file: $INTERVAL_SF2, ./soundfonts/, then macOS sound banks."""
    env = os.environ.get("INTERVAL_SF2")
    if env and os.path.isfile(env):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    patterns = [
        os.path.join(here, "soundfonts", "*.sf2"),
        os.path.expanduser("~/Library/Audio/Sounds/Banks/*.sf2"),
        "/opt/homebrew/share/soundfonts/*.sf2",
        "/usr/local/share/soundfonts/*.sf2",
        "/usr/share/sounds/sf2/*.sf2",
    ]
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    return None


class FluidPiano:
    name = "Piano (FluidSynth)"

    def __init__(self, sf2_path: str):
        import fluidsynth  # raises ImportError if libfluidsynth is missing

        self.synth = fluidsynth.Synth(samplerate=float(SAMPLE_RATE), gain=0.6)
        self.sfid = self.synth.sfload(sf2_path)
        if self.sfid == -1:
            raise RuntimeError(f"could not load soundfont {sf2_path}")
        self.synth.program_select(0, self.sfid, 0, 0)  # bank 0, program 0 = piano
        self.name = f"Piano ({os.path.basename(sf2_path)})"

    def render(self, events: list[NoteEvent], total: float) -> np.ndarray:
        # Turn the note list into time-ordered on/off actions and render
        # audio in between them.
        actions = []
        for ev in events:
            actions.append((ev.start, 1, ev.midi))
            actions.append((ev.start + ev.duration, 0, ev.midi))
        actions.sort()

        chunks = []
        pos = 0
        for t, is_on, midi in actions:
            frame = int(t * SAMPLE_RATE)
            if frame > pos:
                chunks.append(self.synth.get_samples(frame - pos))
                pos = frame
            if is_on:
                self.synth.noteon(0, midi, 90)
            else:
                self.synth.noteoff(0, midi)
        end = int(total * SAMPLE_RATE)
        if end > pos:
            chunks.append(self.synth.get_samples(end - pos))
        data = np.concatenate(chunks).astype(np.int16)
        return data.reshape(-1, 2)

    def reset(self):
        self.synth.all_notes_off(0)


class SimpleSynth:
    """Additive tone with a decaying envelope, vaguely electric-piano-like."""

    name = "Simple synth"

    def _note(self, midi: int, duration: float, length: float) -> np.ndarray:
        freq = 440.0 * 2 ** ((midi - 69) / 12)
        n = int(length * SAMPLE_RATE)
        t = np.arange(n) / SAMPLE_RATE
        wave = np.zeros(n)
        for h in range(1, 9):
            f = freq * h
            if f > SAMPLE_RATE / 2.2:
                break
            # Higher partials are quieter and die out faster.
            decay = 1.2 + 0.6 * h + f / 2000
            wave += np.sin(2 * np.pi * f * t) * np.exp(-decay * t) / h ** 1.4
        attack = np.minimum(1.0, t / 0.005)
        release = np.clip(1.0 - (t - duration) / 0.15, 0.0, 1.0)
        return wave * attack * release

    def render(self, events: list[NoteEvent], total: float) -> np.ndarray:
        n = int(total * SAMPLE_RATE)
        out = np.zeros(n)
        for ev in events:
            start = int(ev.start * SAMPLE_RATE)
            note = self._note(ev.midi, ev.duration, total - ev.start)
            out[start:start + len(note)] += note[: n - start]
        peak = np.max(np.abs(out)) or 1.0
        mono = (out / peak * 0.5 * 32767).astype(np.int16)
        return np.column_stack([mono, mono])

    def reset(self):
        pass


def make_engine():
    sf2 = find_soundfont()
    if sf2:
        try:
            return FluidPiano(sf2)
        except Exception as exc:  # missing libfluidsynth, bad sf2, ...
            print(f"Piano unavailable ({exc}); using simple synth.", file=sys.stderr)
    else:
        print("No .sf2 soundfont found; using simple synth.", file=sys.stderr)
    return SimpleSynth()


# --------------------------------------------------------------------------
# Trainer
# --------------------------------------------------------------------------

class Trainer:
    def __init__(self):
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
        pygame.init()
        self.screen = pygame.display.set_mode((560, 520))
        pygame.display.set_caption("Interval Trainer")
        self.font = pygame.font.SysFont("Helvetica", 20)
        self.big = pygame.font.SysFont("Helvetica", 34, bold=True)
        self.small = pygame.font.SysFont("Helvetica", 15)
        self.channel = pygame.mixer.Channel(0)

        self.engine = make_engine()
        self.semitones: int | None = None
        self.playing = False
        self.note_len = 0.8  # seconds per melodic note; arrows change it
        self.next_at = 0  # pygame ticks when the next interval may start
        self.last_root: int | None = None
        self.current: tuple[int, int] | None = None

    def select(self, semitones: int):
        self.semitones = semitones
        self.playing = True
        self.channel.stop()
        self.next_at = 0

    def toggle(self):
        if self.semitones is None:
            return
        self.playing = not self.playing
        self.channel.stop()
        self.next_at = 0

    def play_next(self):
        root = random.randint(ROOT_LOW, ROOT_HIGH)
        while root == self.last_root:
            root = random.randint(ROOT_LOW, ROOT_HIGH)
        self.last_root = root
        top = root + self.semitones
        self.current = (root, top)

        L = self.note_len
        H = 2 * L  # harmonic chord length
        GAP = 0.15  # short pause between the repeated harmonic chords
        events = [NoteEvent(0.0, L, root), NoteEvent(L, L, top)]
        t = 2 * L
        for i in range(3):
            events += [NoteEvent(t, H, root), NoteEvent(t, H, top)]
            t += H + (GAP if i < 2 else 0.0)
        events += [NoteEvent(t, L, top), NoteEvent(t + L, L, root)]
        total = t + 2 * L + 0.8  # leave room for the release tail
        self.engine.reset()
        sound = pygame.sndarray.make_sound(
            np.ascontiguousarray(self.engine.render(events, total))
        )
        self.channel.play(sound)
        self.next_at = pygame.time.get_ticks() + int((total + 0.4) * 1000)

    def draw(self):
        bg, fg, dim, accent = (24, 26, 32), (230, 230, 235), (120, 125, 140), (90, 170, 255)
        self.screen.fill(bg)

        title = "—"
        if self.semitones is not None:
            title = next(i[2] for i in INTERVALS if i[0] == self.semitones)
        self.screen.blit(self.big.render(title, True, fg), (24, 20))

        status = "Playing" if self.playing else ("Stopped" if self.semitones else "Press a key to start")
        if self.current and self.semitones:
            status += f"   {note_name(self.current[0])} – {note_name(self.current[1])}"
        self.screen.blit(self.font.render(status, True, accent if self.playing else dim), (24, 66))

        y = 110
        for semis, key, name, short in INTERVALS:
            selected = semis == self.semitones
            colour = accent if selected else fg
            if selected:
                pygame.draw.rect(self.screen, (40, 48, 64), (16, y - 3, 528, 26), border_radius=4)
            self.screen.blit(self.font.render(f"[{key}]", True, colour), (24, y))
            self.screen.blit(self.font.render(f"{short:>3}", True, colour), (80, y))
            self.screen.blit(self.font.render(name, True, colour), (130, y))
            self.screen.blit(self.font.render(f"{semis} st", True, dim), (300, y))
            y += 28

        help_lines = [
            f"Space: stop/resume   Up/Down: speed ({self.note_len:.2f}s per note)   Esc: quit",
            f"Sound: {self.engine.name}",
        ]
        for i, line in enumerate(help_lines):
            self.screen.blit(self.small.render(line, True, dim), (24, 460 + i * 22))
        pygame.display.flip()

    def run(self):
        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_SPACE:
                    self.toggle()
                elif event.key in KEY_TO_SEMITONES:
                    self.select(KEY_TO_SEMITONES[event.key])
                elif event.key == pygame.K_UP:
                    self.note_len = max(0.3, self.note_len - 0.1)
                elif event.key == pygame.K_DOWN:
                    self.note_len = min(2.0, self.note_len + 0.1)

            if self.playing and pygame.time.get_ticks() >= self.next_at:
                self.play_next()

            self.draw()
            clock.tick(60)


def main():
    Trainer().run()
    pygame.quit()


if __name__ == "__main__":
    main()
