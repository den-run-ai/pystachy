"""Interactive particle simulation; application and widget logic are Python."""
from miniui import UI, Rect
from raylib_backend import Window


def main() -> None:
    ui = UI(760, 520)
    window = Window(760, 520, "Pystachy miniui prototype")
    running = True
    speed = 0.5
    name = "Pystachy"
    positions = [float(i * 17 % 700) for i in range(150)]
    try:
        while window.open():
            ui.begin(window.poll())
            ui.panel("Pure-Pystachy controls")
            ui.row([0, 0])
            running = ui.checkbox("running", "Run simulation", running)
            if ui.button("reset", "Reset"):
                positions = [float(i * 17 % 700) for i in range(150)]
            ui.row([140, 0])
            ui.label("Speed")
            speed = ui.slider("speed", speed, 0.0, 1.0)
            ui.row([140, 0])
            ui.label("Name")
            name = ui.textbox("name", name, 64)
            ui.row([0])
            ui.label("Hello, " + name)
            ui.progress(speed)
            ui.label("Tab / Shift-Tab: focus. Arrows: edit. Close window to quit.")
            dt = window.dt()
            for i in range(len(positions)):
                if running:
                    positions[i] = (positions[i] + dt * (20.0 + speed * 180.0)) % 700.0
                ui.rectangle(Rect(20 + int(positions[i]), 330 + (i * 13 % 160), 3, 3),
                         ui.style.accent)
            ui.end()
            window.draw(ui)
    finally:
        window.close()


if __name__ == "__main__":
    main()
