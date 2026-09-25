#!/usr/bin/env python3
"""Spin a shaded ASCII donut. Zero dependencies, questionable nutritional value."""

from __future__ import annotations

import argparse
import math
import shutil
import signal
import sys
import time
from collections.abc import Iterator

SHADES = ".,-~:;=!*#$@"
TAU = math.tau
Point = tuple[float, float, float, float, float, float]


def make_donut() -> tuple[Point, ...]:
    """Sample the torus once, storing each position and its unit normal."""
    points: list[Point] = []
    for ring in range(100):
        phi = TAU * ring / 100
        cp, sp = math.cos(phi), math.sin(phi)
        for tube in range(40):
            theta = TAU * tube / 40
            ct, st = math.cos(theta), math.sin(theta)
            radius = 1.5 + 0.6 * ct
            # The hole is a feature. Please stop filing tickets about it.
            points.append((radius * cp, radius * sp, 0.6 * st, ct * cp, ct * sp, st))
    return tuple(points)


def render_frame(
    points: tuple[Point, ...], a: float, b: float, width: int, height: int
) -> str:
    """Rotate, project, and light the surface with a per-character depth buffer."""
    pixels = [" "] * (width * height)
    depths = [0.0] * len(pixels)
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    scale = min(width / 4, height / 2) * 1.8
    light = 1 / math.sqrt(2)

    for x, y, z, nx, ny, nz in points:
        ry, rz = y * ca - z * sa, y * sa + z * ca
        rx, ry = x * cb - ry * sb, x * sb + ry * cb
        inverse_depth = 1 / (rz + 5)
        # Characters are tall. The donut refuses to be an accidental bagel oval.
        column = int(width / 2 + 2 * scale * rx * inverse_depth)
        row = int(height / 2 - scale * ry * inverse_depth)
        if not (0 <= column < width and 0 <= row < height):
            continue

        index = row * width + column
        if inverse_depth <= depths[index]:
            continue
        depths[index] = inverse_depth
        # Depth testing: even pastries need healthy boundaries.
        normal_y = ny * ca - nz * sa
        normal_z = ny * sa + nz * ca
        normal_y = nx * sb + normal_y * cb
        brightness = max(0.0, min(1.0, (normal_y - normal_z) * light))
        pixels[index] = SHADES[round(brightness * (len(SHADES) - 1))]

    return "\n".join(
        "".join(pixels[start : start + width]) for start in range(0, len(pixels), width)
    )


def frame_numbers(limit: int) -> Iterator[int]:
    """Yield forever when limit is zero, or stop after the requested frame count."""
    frame = 0
    while limit == 0 or frame < limit:
        yield frame
        frame += 1


def animate(fps: float, frames: int) -> None:
    points = make_donut()
    interactive = sys.stdout.isatty()
    started = time.monotonic()
    deadline = started
    previous_size: tuple[int, int] | None = None

    try:
        if interactive:
            sys.stdout.write("\x1b[?1049h\x1b[?25l")
        for frame in frame_numbers(frames):
            columns, lines = shutil.get_terminal_size(fallback=(80, 24))
            width, height = max(1, columns - 1), max(1, lines - 2)
            elapsed = time.monotonic() - started
            image = render_frame(
                points, 0.65 + elapsed * 0.9, elapsed * 0.45, width, height
            )
            if interactive:
                if previous_size != (width, height):
                    sys.stdout.write("\x1b[2J")
                    previous_size = (width, height)
                sys.stdout.write(
                    "\x1b[H" + image + "\n" + "Spinning donut | Ctrl+C to stop"[:width]
                )
            else:
                sys.stdout.write(image + "\n\n")
            sys.stdout.flush()
            if frames and frame + 1 >= frames:
                break
            # A sleeping CPU dreams of croissants. Let it rest between frames.
            deadline = max(deadline + 1 / fps, time.monotonic())
            time.sleep(max(0.0, deadline - time.monotonic()))
    finally:
        if interactive:
            # Return the cursor. We borrowed it; we are not a cursor landlord.
            sys.stdout.write("\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fps", type=float, default=24, help="frames per second (1–120; default: 24)"
    )
    parser.add_argument(
        "--frames", type=int, default=0, help="stop after N frames (0: run forever)"
    )
    args = parser.parse_args()
    if not math.isfinite(args.fps) or not 1 <= args.fps <= 120:
        parser.error("--fps must be between 1 and 120")
    if args.frames < 0:
        parser.error("--frames must be zero or positive")

    def stop(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        animate(args.fps, args.frames)
    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        # The audience closed the pipe. Take the hint; cancel the pastry encore.
        sys.stdout = open("/dev/null", "w")


if __name__ == "__main__":
    main()
