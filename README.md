# GPX Checkpoint Inserter

A command-line utility to insert race checkpoints (waypoints) into a GPX file, with optional track simplification for file size reduction.

Originally built for [XTRAIL](https://livetrail.run) races exported from LiveTrail, but works with any GPX file that includes `<extensions><distance>` metadata on track points.

## Features

- Insert named checkpoints as `<wpt>` waypoints at precise route distances
- Print existing checkpoints in a GPX file
- Simplify track using the [Douglas-Peucker algorithm](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm) to drastically reduce file size
- Supports Unicode checkpoint names (Chinese, Japanese, etc.)
- Never overwrites the input file — always saves to a new `_with_checkpoints.gpx`

## Requirements

Python 3.6+ — no third-party dependencies.

## Usage

### Print existing checkpoints in a GPX file

```bash
python3 insert_checkpoints.py <gpx_file>
```

Example output:
```
#    Name                                       Lat         Lon    Ele
----------------------------------------------------------------------
1    Start - 墾丁青年活動中心              21.94191   120.80023   16.5m
2    CP1 - 墾丁牧場VILLA-2                21.95585   120.78503   23.0m
...
```

### Insert checkpoints from a CSV file

```bash
python3 insert_checkpoints.py <gpx_file> <csv_file>
```

Output is saved as `<gpx_file_stem>_with_checkpoints.gpx`.

### Insert checkpoints with track simplification

```bash
python3 insert_checkpoints.py <gpx_file> <csv_file> --simplify [tolerance_m]
```

`tolerance_m` is the Douglas-Peucker tolerance in meters (default: `10`). Lower values preserve more detail; higher values produce smaller files.

| Tolerance | Points kept | File size (98km track) |
|-----------|-------------|------------------------|
| none      | 13,309      | 2.10 MB                |
| `--simplify 5`  | 1,872 (14%) | 0.13 MB          |
| `--simplify 10` | 1,145 (9%)  | 0.08 MB          |
| `--simplify 20` | 702 (5%)    | 0.05 MB          |

Simplification also strips LiveTrail `<extensions>` metadata and rounds coordinates to 6 decimal places (~0.1m precision).

## CSV Format

The CSV file must have a header row. The first column is the checkpoint name, the second is the distance from the start in kilometres.

```csv
點,距離 (km)
Start - 墾丁青年活動中心,0
CP1 - 墾丁牧場VILLA-2,11.6
CP2 - 潭仔巷舊屋,17.8
Finish - 墾丁青年活動中心,98.3
```

See [`checkpoints_sample.csv`](checkpoints_sample.csv) for a complete English example and [`checkpoints_zh.csv`](checkpoints_zh.csv) for a Chinese example.

Each checkpoint is matched to the track point whose cumulative distance is closest to the specified value, so minor rounding in the CSV is fine.

## Examples

```bash
# View checkpoints already embedded in a GPX
python3 insert_checkpoints.py race.gpx

# Insert English checkpoints (keeps original file size)
python3 insert_checkpoints.py race.gpx checkpoints_sample.csv

# Insert Chinese checkpoints with simplification for Strava upload (< 1 MB limit)
python3 insert_checkpoints.py race.gpx checkpoints_zh.csv --simplify 5

# Aggressive simplification for small devices or slow connections
python3 insert_checkpoints.py race.gpx checkpoints_zh.csv --simplify 20
```

## GPX Compatibility

| Viewer / App | Waypoint support | Notes |
|---|---|---|
| [GPX Studio](https://gpx.studio) | ✅ | Full support |
| Garmin devices | ✅ | Full support |
| Strava | ⚠️ | 1 MB file size limit; use `--simplify` |
| Google Maps | ❌ | Does not display waypoints |

## LiveTrail GPX Format

LiveTrail exports include a non-standard `<distance>` extension on every track point:

```xml
<trkpt lat="21.94191" lon="120.80023">
  <ele>16.5</ele>
  <extensions>
    <distance>0</distance>   <!-- cumulative distance in metres -->
  </extensions>
</trkpt>
```

This script uses that field to locate the correct track point for each checkpoint distance. When `--simplify` is used, the extensions are removed and a clean standard-compliant GPX is written.
