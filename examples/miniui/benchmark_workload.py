"""Deterministic benchmark of the unchanged miniui implementation.

The controls and particle update match demo.py. A fixed 1/60 s step and bounded
frame count make runtimes comparable; no frame pacing is included in timings.
This module remains import-safe for CPython, Cython and Pystachy.
"""
import time

from miniui import Input, Rect, UI
from raylib_backend import Window, _rect
from benchmark_control import configure, reset, calls, digest, snapshot


class State:
    def __init__(self, particles: int):
        self.ui = UI(760, 520)
        self.running = True
        self.speed = 0.5
        self.name = "Pystachy"
        self.positions: list[float] = [float(i * 17 % 700) for i in range(particles)]

    def simulate(self) -> None:
        positions = self.positions
        running = self.running
        speed = self.speed
        dt = 1.0 / 60.0
        for i in range(len(positions)):
            if running:
                positions[i] = (positions[i] + dt * (20.0 + speed * 180.0)) % 700.0

    def make_ui(self, events: Input, advance: bool = False) -> None:
        ui = self.ui
        ui.begin(events)
        ui.panel("Pure-Pystachy controls")
        ui.row([0, 0])
        self.running = ui.checkbox("running", "Run simulation", self.running)
        if ui.button("reset", "Reset"):
            self.positions = [float(i * 17 % 700) for i in range(len(self.positions))]
        ui.row([140, 0])
        ui.label("Speed")
        self.speed = ui.slider("speed", self.speed, 0.0, 1.0)
        ui.row([140, 0])
        ui.label("Name")
        self.name = ui.textbox("name", self.name, 64)
        ui.row([0])
        ui.label("Hello, " + self.name)
        ui.progress(self.speed)
        ui.label("Tab / Shift-Tab: focus. Arrows: edit. Close window to quit.")
        positions = self.positions
        running = self.running
        speed = self.speed
        dt = 1.0 / 60.0
        for i in range(len(positions)):
            if advance and running:
                positions[i] = (positions[i] + dt * (20.0 + speed * 180.0)) % 700.0
            ui.rectangle(Rect(20 + int(positions[i]), 330 + (i * 13 % 160), 3, 3),
                         ui.style.accent)
        ui.end()

    def checksum(self) -> int:
        value = 1
        events = self.ui.input
        for item in [int(self.running), int(self.speed * 1000000.0), self.ui.cursor,
                     events.x, events.y, int(events.down), int(events.pressed),
                     int(events.released), int(events.focused), int(events.backspace),
                     int(events.delete), int(events.left), int(events.right),
                     int(events.home), int(events.end), int(events.tab), int(events.shift),
                     int(events.enter), int(events.space), int(events.escape)]:
            value = (value * 65599 + item) % 2147483647
        for text in [self.name, self.ui.focus, self.ui.active, events.text]:
            for char in text:
                value = (value * 65599 + ord(char)) % 2147483647
        for position in self.positions:
            value = (value * 65599 + int(position * 1000000.0)) % 2147483647
        for command in self.ui.commands:
            for item in [command.kind, command.rect.x, command.rect.y,
                         command.rect.w, command.rect.h, command.clip.x,
                         command.clip.y, command.clip.w, command.clip.h,
                         command.color, command.size, command.caret]:
                value = (value * 65599 + item) % 2147483647
            for char in command.text:
                value = (value * 65599 + ord(char)) % 2147483647
        return value


def loop(state: State, window: Window, mode: str, frames: int) -> None:
    if mode == "simulate":
        for _ in range(frames):
            state.simulate()
    elif mode == "ui":
        for _ in range(frames):
            state.make_ui(Input())
    elif mode == "submit":
        for _ in range(frames):
            window.draw(state.ui)
    elif mode == "poll":
        for _ in range(frames):
            state.ui.input = window.poll()
    elif mode == "frame":
        for _ in range(frames):
            events = window.poll()
            state.make_ui(events, True)
            window.draw(state.ui)
    elif mode == "ffi":
        for i in range(frames):
            _rect(i % 700, 340, 3, 3, 0x66C2FFFF)
    else:
        raise ValueError("unknown benchmark mode")


def run(mode: str, particles: int, frames: int, warmup: int,
        image_path: str = "") -> None:
    if particles < 1 or frames < 1 or warmup < 0:
        raise ValueError("positive particles/frames and nonnegative warmup required")
    state = State(particles)
    window = Window(760, 520, "miniui benchmark")
    try:
        configure()
        state.make_ui(Input())
        loop(state, window, mode, warmup)
        reset()
        started = time.perf_counter()
        loop(state, window, mode, frames)
        elapsed = time.perf_counter() - started
        operation_count = calls()
        operation_hash = digest()
        if image_path:
            # Redraw and capture outside the timed and checksummed interval.
            window.draw(state.ui)
            if snapshot(image_path) == 0:
                raise RuntimeError("framebuffer snapshot failed")
        print("RESULT", mode, particles, frames, warmup, elapsed,
              state.checksum(), len(state.ui.commands), operation_count, operation_hash)
    finally:
        window.close()
