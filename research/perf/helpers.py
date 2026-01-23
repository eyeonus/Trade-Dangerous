from __future__ import annotations
from pathlib import Path
import math
import time
import typing
import sys

ANSI_CURS_UP = "\x1b[1A\x1B[K" if sys.stdout.isatty() else ""

# Make sure that the project root is in the import path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def iterate(op: callable, *, cases: typing.Any = None, iterations: int, display: int = 10, label: str = None) -> list[float]:
    """ makes calls to a particular callable for N iterations and returns the sorted list of timings.
        prints progress every 'display' iterations, unless display is 0.
        progress display is prefixed with 'label' or 'Iteration'
    """
    label = label or "Iteration"        # What to call ourselves
    max_iter = f"{iterations:n}"        # So we can size the current iteration similarly
    timings = []                        # Where we're going to capture the timings

    if ANSI_CURS_UP:
        print("")  # reserve ourselves a clean line

    run_start = time.time()
    for i in range(iterations):
        if display and i % display == 0:
            now = time.time()
            print(f"{ANSI_CURS_UP}{label} {i+1:{len(max_iter)}n}/{max_iter} ({now - run_start:.3f}s)")

        iter_start = time.time()
        if cases:
            for case in cases:
                op(case)
        else:
            op()
        timings += [time.time() - iter_start]

    timings.sort()

    print(f"{ANSI_CURS_UP}{label} {max_iter} iters took {sum(timings):.3f}s, bench {time.time() - run_start:.3f}s")

    return timings


def percentile(sorted_values: list[float | int] | tuple[float | int], point: float) -> float | int:
    """ return the Nth percentile value from a sorted list of values.
        point must be a value between 0-100,
        sorted_values must be a list or tuple that has been sorted """
    if point <= 0:
        if point < 0:
            raise ValueError("negative percentile index")
        return values[0]
    if point >= 100:
        if point > 100:
            raise ValueError("percentile > 100 is meaningless")
        return values[-1]

    # calculate the element index as a float value; e.g. the 50th percentile
    # of a list containing 2 items is midway between two items - 0th and 1th elements.
    # the 50th percentile for a list containing 100 items is between the 49th 50th element
    # the 95th percentile for a list containing 10 items is between 8 and 9, but should
    # lean closer to the 9th value, so we interpolate
    fpoint = (point / 100) * (len(sorted_values) - 1)  # think of this as "gap constraining"
    index = int(fpoint)
    frac = fpoint - index
    if math.isclose(frac, 0):
      return sorted_values[index]
    # linear interpolated 'average' between the two values
    return sorted_values[index] * (1 - frac) + sorted_values[index + 1] * frac
