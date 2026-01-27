from datetime import datetime, timezone, timedelta
import math
import time

import helpers

from tradedangerous.db.utils import parse_ts

cases = [
    None,

    1,                          
    86400 * 42 * 365,
    86400 * 24 * 365 * 3.141,
] + list(
 datetime(1970, 1, 1, 1, 0, 0, 0, tzinfo=zone) for zone in [timezone.utc, timezone(timedelta(hours=-1)), timezone(timedelta(hours=2, minutes=30))]
) + list(
 datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=zone) for zone in [timezone.utc, timezone(timedelta(hours=-8)), timezone(timedelta(hours=5))]
) + [
  "2020-01-01T00:00:00.000",
  "2020-01-01T00:00:00+0000",
  "2020-01-01T00:00:00+00:00",
  "2020-01-01 00:00:00+00:00",
  "2020-01-01Z00:00:00",
]

# Make a lot of cases
cases = cases * 307

# Do a few thousand repeats of them all
iterations = 5003

timings = helpers.iterate(parse_ts, cases=cases, iterations=iterations, display=100)

# Timings are in seconds, multiply to milliseconds
timings[:] = [t*1000 for t in timings]

best, timings, worst = timings[0], timings[1:-1], timings[-1]
avg = sum(timings) / len(timings)

p10 = helpers.percentile(timings, 10)
p25 = helpers.percentile(timings, 25)
p50 = helpers.percentile(timings, 50)
p90 = helpers.percentile(timings, 90)
p99 = helpers.percentile(timings, 99)

print(
  f"ex-best: {best:.3f}ms, "
  f"best: {timings[0]:.3f}ms, "
  f"avg: {avg:.3f}ms, "
  f"worst: {timings[-1]:.3f}ms, "
  f"ex-worst: {worst:.3f}ms, "
)
print(
  f"p10: {p10:.3f}ms, "
  f"p25: {p25:.3f}ms, "
  f"p50: {p50:.3f}ms, "
  f"p90: {p90:.3f}ms, "
  f"p99: {p99:.3f}ms, "
)

  
