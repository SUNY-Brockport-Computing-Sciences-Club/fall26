#!/usr/bin/env python3
"""Spin an ASCII toy locomotive. No dependencies. Extremely local public transit."""

from __future__ import annotations

import argparse
import math
import os
import shutil
import signal
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass

SHADES = ".,-~:;=!*#$@"
TAU = math.tau
Vector = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Point:
    position: Vector
    normal: Vector
    glyph: str | None = None


def samples(start: float, end: float, spacing: float = 0.07) -> Iterator[float]:
    """Include both endpoints while keeping surface samples close together."""
    count = max(1, math.ceil(abs(end - start) / spacing))
    for index in range(count + 1):
        yield start + (end - start) * index / count


def make_train() -> tuple[Point, ...]:
    """Build a locomotive from closed boxes and capped cylinders."""
    points: list[Point] = []

    def add_point(
        position: list[float], normal: list[float], glyph: str | None = None
    ) -> None:
        points.append(
            Point(
                (position[0], position[1], position[2]),
                (normal[0], normal[1], normal[2]),
                glyph,
            )
        )

    def box(low: Vector, high: Vector, glyph: str | None = None) -> None:
        for axis in range(3):
            u, v = (axis + 1) % 3, (axis + 2) % 3
            for side, direction in ((low[axis], -1.0), (high[axis], 1.0)):
                for first in samples(low[u], high[u]):
                    for second in samples(low[v], high[v]):
                        position = [0.0, 0.0, 0.0]
                        normal = [0.0, 0.0, 0.0]
                        position[axis], position[u], position[v] = side, first, second
                        normal[axis] = direction
                        add_point(position, normal, glyph)

    def cylinder(center: Vector, radius: float, length: float, axis: int) -> None:
        u, v = (axis + 1) % 3, (axis + 2) % 3
        for segment in range(72):
            angle = TAU * segment / 72
            cosine, sine = math.cos(angle), math.sin(angle)
            normal = [0.0, 0.0, 0.0]
            normal[u], normal[v] = cosine, sine
            for offset in samples(-length / 2, length / 2):
                position = list(center)
                position[axis] += offset
                position[u] += radius * cosine
                position[v] += radius * sine
                add_point(position, normal)

        # Cap the ends. An uncapped boiler is just a very ambitious kazoo.
        for side in (-1, 1):
            normal = [0.0, 0.0, 0.0]
            normal[axis] = float(side)
            for first in samples(-radius, radius):
                for second in samples(-radius, radius):
                    if first * first + second * second > radius * radius:
                        continue
                    position = list(center)
                    position[axis] += side * length / 2
                    position[u] += first
                    position[v] += second
                    add_point(position, normal)

    # Chassis: all aboard the world's least useful commuting option.
    box((-2.35, -0.55, -0.63), (2.4, -0.28, 0.63))
    cylinder((0.65, 0.23, 0.0), radius=0.56, length=2.7, axis=0)
    cylinder((2.04, 0.23, 0.0), radius=0.59, length=0.13, axis=0)
    cylinder((2.15, 0.23, 0.0), radius=0.18, length=0.12, axis=0)

    # Cab, roof, and windows. The conductor demanded an office with a view.
    box((-2.05, -0.28, -0.62), (-0.72, 1.02, 0.62))
    box((-2.22, 1.02, -0.78), (-0.55, 1.22, 0.78))
    for side in (-1, 1):
        z = side * 0.635
        box((-1.86, 0.32, z - 0.008), (-0.93, 0.83, z + 0.008), " ")
        box((-1.43, 0.29, z - 0.014), (-1.36, 0.86, z + 0.014))
    box((-0.708, 0.4, -0.39), (-0.698, 0.85, 0.39), " ")
    box((-2.07, 0.32, -0.38), (-2.06, 0.82, 0.38), " ")

    # Chimney and steam dome. Emissions currently consist of ASCII characters.
    cylinder((1.38, 1.05, 0.0), radius=0.19, length=0.85, axis=1)
    cylinder((1.38, 1.49, 0.0), radius=0.29, length=0.19, axis=1)
    cylinder((0.05, 0.81, 0.0), radius=0.23, length=0.27, axis=1)

    # Six wheels, zero steering wheels. Railways really committed to the bit.
    for x in (-1.63, -0.05, 1.5):
        for side in (-1, 1):
            cylinder((x, -0.67, side * 0.68), radius=0.4, length=0.2, axis=2)
            cylinder((x, -0.67, side * 0.81), radius=0.13, length=0.09, axis=2)
    for side in (-1, 1):
        z = side * 0.875
        box((-1.63, -0.71, z - 0.025), (1.5, -0.63, z + 0.025))
    box((2.36, -0.49, -0.78), (2.61, -0.32, 0.78))
    box((-2.59, -0.49, -0.18), (-2.34, -0.36, 0.18))
    return tuple(points)


def render_frame(
    points: tuple[Point, ...], yaw: float, pitch: float, width: int, height: int
) -> str:
    """Rotate, project, and light the surface with a per-character depth buffer."""
    pixels = [" "] * (width * height)
    depths = [0.0] * len(pixels)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    scale = min(width / 12, height / 4.6) * 7
    light = 1 / math.sqrt(2)

    for point in points:
        x, y, z = point.position
        nx, ny, nz = point.normal
        rx, rz = x * cy + z * sy, -x * sy + z * cy
        ry, rz = y * cp + rz * sp, -y * sp + rz * cp
        inverse_depth = 1 / (rz + 7)
        # Terminal cells are tall. Compensate before the train becomes a tram.
        column = int(width / 2 + 2 * scale * rx * inverse_depth)
        row = int(height * 0.56 - scale * ry * inverse_depth)
        if not (0 <= column < width and 0 <= row < height):
            continue

        index = row * width + column
        if inverse_depth <= depths[index]:
            continue
        depths[index] = inverse_depth
        # The nearest surface wins. Finally, a fair railway boarding policy.
        normal_z = -nx * sy + nz * cy
        normal_y, normal_z = ny * cp + normal_z * sp, -ny * sp + normal_z * cp
        brightness = max(0.0, min(1.0, (normal_y - normal_z) * light))
        pixels[index] = (
            point.glyph
            if point.glyph is not None
            else SHADES[round(brightness * (len(SHADES) - 1))]
        )

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
    points = make_train()
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
                points, 0.35 + elapsed * 0.65, 0.22, width, height
            )
            if interactive:
                if previous_size != (width, height):
                    sys.stdout.write("\x1b[2J")
                    previous_size = (width, height)
                sys.stdout.write(
                    "\x1b[H"
                    + image
                    + "\n"
                    + "Spinning toy train | Choo choo! | Ctrl+C to stop"[:width]
                )
            else:
                sys.stdout.write(image + "\n\n")
            sys.stdout.flush()
            if frames and frame + 1 >= frames:
                break
            # Mandatory station stop: give the CPU time to question its career.
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
        # The audience closed the tunnel. Cancel the remaining departures.
        sys.stdout = open(os.devnull, "w")


if __name__ == "__main__":
    main()
