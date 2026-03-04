#!/usr/bin/env python3
"""
Insert checkpoints as waypoints into a GPX file, with optional track simplification.

Usage:
    python3 insert_checkpoints.py <gpx_file>
        Print existing checkpoints in the GPX file.

    python3 insert_checkpoints.py <gpx_file> <csv_file>
        Insert checkpoints from CSV as waypoints into the GPX file.

    python3 insert_checkpoints.py <gpx_file> <csv_file> --simplify [tolerance_m]
        Insert checkpoints and simplify the track (default tolerance: 10m).
        Removes LiveTrail extensions, rounds coordinates to 6 decimal places,
        and applies Douglas-Peucker to reduce point count.

CSV format (with header):
    name,distance_km
    Kenting Youth Activity Center,0
    Some Checkpoint,11.6
    ...
"""

import re
import csv
import sys
import math
import argparse
from pathlib import Path


def parse_track_points(content):
    """Parse track points with LiveTrail distance metadata."""
    pattern = re.compile(
        r'<trkpt lat="([^"]+)" lon="([^"]+)">\s*<ele>([^<]+)</ele>\s*<extensions>\s*<distance>([^<]+)</distance>'
    )
    return [(float(m[1]), float(m[2]), float(m[3]), float(m[4])) for m in pattern.finditer(content)]


def find_nearest_point(points, target_m):
    return min(points, key=lambda p: abs(p[3] - target_m))


def load_checkpoints(csv_file):
    checkpoints = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) >= 2:
                name = row[0].strip()
                distance_km = float(row[1].strip())
                checkpoints.append((name, distance_km * 1000))
    return checkpoints


def build_wpt_element(name, lat, lon, ele):
    return f'  <wpt lat="{lat}" lon="{lon}">\n    <ele>{ele}</ele>\n    <name>{name}</name>\n  </wpt>'


def print_checkpoints(content):
    pattern = re.compile(
        r'<wpt lat="([^"]+)" lon="([^"]+)">\s*<ele>([^<]+)</ele>\s*<name>([^<]+)</name>'
    )
    waypoints = pattern.findall(content)
    if not waypoints:
        print("No checkpoints (waypoints) found in GPX file.")
        return
    print(f"{'#':<4} {'Name':<35} {'Lat':>10} {'Lon':>11} {'Ele':>6}")
    print("-" * 70)
    for i, (lat, lon, ele, name) in enumerate(waypoints, 1):
        print(f"{i:<4} {name:<35} {lat:>10} {lon:>11} {float(ele):>6.1f}m")


# --- Douglas-Peucker simplification ---

def perp_distance_m(point, line_start, line_end):
    """Perpendicular distance in meters from point to line segment (lat/lon coords)."""
    lat_scale = 111000.0
    lon_scale = 111000.0 * math.cos(math.radians(line_start[0]))
    px = (point[1] - line_start[1]) * lon_scale
    py = (point[0] - line_start[0]) * lat_scale
    dx = (line_end[1] - line_start[1]) * lon_scale
    dy = (line_end[0] - line_start[0]) * lat_scale
    line_len_sq = dx * dx + dy * dy
    if line_len_sq == 0:
        return math.sqrt(px * px + py * py)
    t = max(0.0, min(1.0, (px * dx + py * dy) / line_len_sq))
    return math.sqrt((px - t * dx) ** 2 + (py - t * dy) ** 2)


def douglas_peucker(points, tolerance_m):
    """Iterative Douglas-Peucker. Returns sorted list of indices to keep."""
    n = len(points)
    if n <= 2:
        return list(range(n))

    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]

    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        max_dist, max_idx = 0.0, start
        for i in range(start + 1, end):
            d = perp_distance_m(points[i], points[start], points[end])
            if d > max_dist:
                max_dist, max_idx = d, i
        if max_dist > tolerance_m:
            keep[max_idx] = True
            stack.append((start, max_idx))
            stack.append((max_idx, end))

    return [i for i, k in enumerate(keep) if k]


def build_simplified_gpx(points, simplified_indices, wpt_elements):
    """Build a clean GPX string with simplified track and waypoints."""
    trkpts = [
        f'      <trkpt lat="{points[i][0]:.6f}" lon="{points[i][1]:.6f}"><ele>{points[i][2]}</ele></trkpt>'
        for i in simplified_indices
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx creator="insert_checkpoints.py" version="1.1" xmlns="http://www.topografix.com/GPX/1/1">',
        '  <trk>',
        '    <trkseg>',
        *trkpts,
        '    </trkseg>',
        '  </trk>',
        *wpt_elements,
        '</gpx>',
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Insert checkpoints into a GPX file.")
    parser.add_argument("gpx_file", help="Input GPX file")
    parser.add_argument("csv_file", nargs="?", help="CSV file with checkpoint names and distances (km)")
    parser.add_argument(
        "--simplify", nargs="?", const=10.0, type=float, metavar="TOLERANCE_M",
        help="Simplify track using Douglas-Peucker (default tolerance: 10m)"
    )
    args = parser.parse_args()

    gpx_path = Path(args.gpx_file)
    if not gpx_path.exists():
        print(f"Error: GPX file not found: {gpx_path}")
        sys.exit(1)

    content = gpx_path.read_text(encoding="utf-8")

    # Print-only mode
    if args.csv_file is None:
        print_checkpoints(content)
        return

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    points = parse_track_points(content)
    if not points:
        print("Error: No track points with distance metadata found in GPX file.")
        sys.exit(1)

    checkpoints = load_checkpoints(csv_path)
    if not checkpoints:
        print("Error: No checkpoints found in CSV file.")
        sys.exit(1)

    print(f"Track points: {len(points)}, max distance: {points[-1][3]:.0f}m")
    print(f"Checkpoints to insert: {len(checkpoints)}\n")

    wpt_elements = []
    for name, target_m in checkpoints:
        lat, lon, ele, matched_m = find_nearest_point(points, target_m)
        print(f"  {name}: target={target_m:.0f}m, matched={matched_m:.0f}m")
        wpt_elements.append(build_wpt_element(name, lat, lon, ele))

    if args.simplify is not None:
        tolerance = args.simplify
        print(f"\nSimplifying track (tolerance={tolerance}m)...")
        indices = douglas_peucker(points, tolerance)
        pct = len(indices) / len(points) * 100
        print(f"  Points: {len(points)} → {len(indices)} ({pct:.1f}% kept)")
        new_content = build_simplified_gpx(points, indices, wpt_elements)
    else:
        wpt_block = "\n".join(wpt_elements)
        new_content = content.replace("</gpx>", wpt_block + "\n</gpx>")

    out_path = gpx_path.with_stem(gpx_path.stem + "_with_checkpoints")
    out_path.write_text(new_content, encoding="utf-8")
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nDone! Saved to {out_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
