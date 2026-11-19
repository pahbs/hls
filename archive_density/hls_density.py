"""HLS archive density: observed and clear days, from the daily global HLS masks (see PLAN.md).

    python hls_density.py aggregate 2020        # one year of daily masks -> STORE/<year>.npz (run years side by side)
    python hls_density.py build                  # STORE -> site/index.html + site/data/*.bin
    python hls_density.py publish                # site/ -> the gh-pages branch (one commit, replaced each time)

The masks: one GeoTIFF a day, 0/1 (observed, or observed clear), about 0.009 deg, lat/lon, Landsat and Sentinel-2
together. Each day is counted per CELL (0.1 deg) cell: the number of pixels observed (and clear) that day, at most ~144
a cell, so uint8. The store keeps every day and the cells HLS observed in the year, so coarser grids, daily views and
revisit statistics can be made later without reading the rasters again.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SRC = Path("/panfs/ccds02/nobackup/projects/hls/HLS/qzhou2/Cloudprob/Revisit_all/Mosaic/revisit_ts/Global")
MASKS = {"obs": "daily_masks", "clear": "daily_clear_masks"}
STORE = Path(os.environ.get("HLS_DENSITY_STORE", "/explore/nobackup/people/pmontesa/hls_archive_density/store"))
HERE = Path(__file__).resolve().parent
CELL = 0.1                      # store grid (deg); cell index = row * COLUMNS + col, row 0 at 90 N
COLUMNS = int(round(360 / CELL))


def _grid(transform, width: int, height: int):
    """Pixel columns and rows grouped into CELL cells: the start of each run, and the cell column / row it falls in."""
    lon = transform.c + (np.arange(width) + 0.5) * transform.a
    lat = transform.f + (np.arange(height) + 0.5) * transform.e
    cc = np.clip(np.floor((lon + 180) / CELL).astype(int), 0, COLUMNS - 1)
    rr = np.clip(np.floor((90 - lat) / CELL).astype(int), 0, int(round(180 / CELL)) - 1)
    c0 = np.flatnonzero(np.r_[True, np.diff(cc) != 0])
    r0 = np.flatnonzero(np.r_[True, np.diff(rr) != 0])
    return c0, cc[c0], r0, rr[r0]


def _count(a: np.ndarray, grid, also: np.ndarray = None) -> np.ndarray:
    """Pixels equal to 1 (and also 1 in `also`), summed per cell: (cell rows, cell columns) of the raster's extent."""
    c0, _, r0, _ = grid
    hit = a == 1
    if also is not None:
        hit &= also == 1
    s = np.add.reduceat(hit.view(np.uint8), c0, axis=1, dtype=np.uint16)
    return np.add.reduceat(s, r0, axis=0, dtype=np.uint16)


def aggregate(year: int) -> Path:
    """One year: per day and cell, the pixels observed and the pixels clear; per cell, the pixels observed at least once
    in the year. Days whose clear mask is missing have no clear row (clear_days lists the days that do)."""
    import rasterio
    STORE.mkdir(parents=True, exist_ok=True)
    out = STORE / f"{year}.npz"
    files = sorted((SRC / MASKS["obs"] / str(year)).glob("mask_*.tif"))[:int(os.environ.get("HLS_DENSITY_DAYS", 400))]   # fewer: a quick test
    if not files:
        raise SystemExit(f"no masks for {year}")
    with rasterio.open(files[0]) as r:
        grid, shape = _grid(r.transform, r.width, r.height), (r.height, r.width)
    rows, cols = grid[3], grid[1]
    cell_index = (rows[:, None] * COLUMNS + cols[None, :]).ravel()
    ever = np.zeros(shape, bool)
    days, obs, clear_days, clear = [], [], [], []
    started = time.time()
    for k, f in enumerate(files):
        doy = int(f.stem[-3:])
        with rasterio.open(f) as r:
            a = r.read(1)
        ever |= a == 1
        days.append(doy)
        obs.append(_count(a, grid).ravel().astype(np.uint8))
        cf = SRC / MASKS["clear"] / str(year) / f.name
        if cf.exists():
            with rasterio.open(cf) as r:
                c = r.read(1)
            clear_days.append(doy)
            clear.append(_count(c, grid, also=a).ravel().astype(np.uint8))   # clear only where observed: the clear masks
            # also mark pixels that were not observed (a line along the equator every day, other seams), 0.07% of clear pixels
        if k % 30 == 0:
            print(f"{year}: day {doy} ({k + 1} of {len(files)}), {time.time() - started:.0f} s", flush=True)
    land = _count(ever.view(np.uint8), grid).ravel()          # pixels observed at least once this year
    keep = np.flatnonzero(land > 0)
    tmp = out.with_name(out.name + ".tmp.npz")
    np.savez_compressed(tmp, year=year, cell=CELL, cells=cell_index[keep].astype(np.int32), land=land[keep].astype(np.uint8),
                        days=np.array(days, np.int16), obs=np.stack(obs)[:, keep],
                        clear_days=np.array(clear_days, np.int16),
                        clear=np.stack(clear)[:, keep] if clear else np.zeros((0, len(keep)), np.uint8))
    os.replace(tmp, out)
    np.save(STORE / f"ever_{year}.npy", np.packbits(ever))  # the year's observed pixels, for a land area over all years
    print(f"{year}: {len(days)} days ({len(clear_days)} with a clear mask), {len(keep)} cells; {out} "
          f"{out.stat().st_size / 1e6:.0f} MB, {time.time() - started:.0f} s", flush=True)
    return out


# ---- the page
SITE = HERE / "_site"                     # what is published: _site/archive_density/{index.html, data/*.bin}
PAGE_DIR = SITE / "archive_density"
TEMPLATE = HERE / "template.html"         # forked from csda_summaries lib/archive_density_template.html (30c0695)
LAND = HERE / "land.txt"                  # land outline (SVG path, x = lon + 180, y = 90 - lat), as on the CSDA page
OUT_CELL = 0.5                            # page grid (deg): a multiple of CELL
DIV = 8                                   # values stored in eighths of a day: 31 days = 248, one byte
START = "2013-04"                         # first month with masks (Landsat 8 from 11 Apr 2013)
PALETTE = {"color": "#0000FF",            # the CSDA pages' USGS / NASA palette (archive_dashboard.vendor_palette)
           "light": ["#d0defc", "#a7c4fe", "#7ba5fe", "#5084fd", "#205cff", "#0033ea", "#0022b0"],
           "dark": ["#0029c2", "#0035f9", "#2762fd", "#5488fd", "#80a9ff", "#acc7fe", "#d5e2fc"],
           "map_light": ["#7ba5fe", "#5488fd", "#2c66fe", "#013afd", "#0002e0", "#0001a7"],
           "map_dark": ["#114dfc", "#3b74fd", "#6494fc", "#8bb0fd", "#b1cbff", "#d8e5ff"]}
REMOTE = "git@github.com:pahbs/hls.git"


def _land(years) -> np.ndarray:
    """Pixels HLS observed at least once in any of these years, per CELL cell (full grid, row 0 at 90 N)."""
    import rasterio
    with rasterio.open(sorted((SRC / MASKS["obs"] / str(years[0])).glob("mask_*.tif"))[0]) as r:
        grid, shape = _grid(r.transform, r.width, r.height), (r.height, r.width)
    ever = None
    for y in years:
        bits = np.unpackbits(np.load(STORE / f"ever_{y}.npy"), count=shape[0] * shape[1]).view(bool)
        ever = bits if ever is None else ever | bits
    full = np.zeros(int(round(180 / CELL)) * COLUMNS, np.int64)
    full[(grid[3][:, None] * COLUMNS + grid[1][None, :]).ravel()] = _count(ever.reshape(shape).view(np.uint8), grid).ravel()
    return full


def build(cell: float = OUT_CELL) -> Path:
    """Monthly means per page cell, from every year in the store: observed and clear days per land pixel."""
    import calendar
    years = sorted(int(p.stem) for p in STORE.glob("[0-9][0-9][0-9][0-9].npz"))
    if not years:
        raise SystemExit("nothing aggregated yet")
    land01 = _land(years)
    f, cols_out = int(round(cell / CELL)), int(round(360 / cell))
    to_out = lambda idx: (idx // COLUMNS // f) * cols_out + (idx % COLUMNS) // f
    land_out = np.bincount(to_out(np.flatnonzero(land01)), weights=land01[land01 > 0], minlength=cols_out * int(round(180 / cell)))
    keep = np.flatnonzero(land_out > 0)
    pos = np.full(land_out.size, -1)
    pos[keep] = np.arange(len(keep))
    land_keep, land_all = land_out[keep], land_out.sum()
    months = [f"{y}-{m:02d}" for y in years for m in range(1, 13) if f"{y}-{m:02d}" >= START]
    obs_out = np.zeros((len(months), len(keep)), np.uint8)
    clear_out = np.zeros_like(obs_out)
    totals = []
    for y in years:
        z = np.load(STORE / f"{y}.npz")
        obs, clear, cells = z["obs"], z["clear"], z["cells"]
        at = pos[to_out(cells.astype(np.int64))]
        month_of = lambda doys: (np.datetime64(f"{y}-01-01") + (doys.astype(int) - 1)).astype("datetime64[M]").astype(int) % 12 + 1
        dm, cm = month_of(z["days"]), month_of(z["clear_days"])
        for m in range(1, 13):
            key = f"{y}-{m:02d}"
            if key not in months:
                continue
            i, sel, csel = months.index(key), dm == m, cm == m
            row = {"month": key, "mask_days": int(sel.sum()), "month_days": calendar.monthrange(y, m)[1], "sensors": {}}
            o = np.bincount(at, weights=obs[sel].sum(axis=0, dtype=np.int64), minlength=len(keep))
            obs_out[i] = np.clip(np.round(o / land_keep * DIV), 0, 255)
            row["obs"] = row["n"] = round(float(o.sum() / land_all), 3)
            row["clear_ok"] = bool(sel.sum()) and int(csel.sum()) == int(sel.sum())
            if row["clear_ok"]:
                c = np.bincount(at, weights=clear[csel].sum(axis=0, dtype=np.int64), minlength=len(keep))
                clear_out[i] = np.clip(np.round(c / land_keep * DIV), 0, 255)
                row["clear"] = round(float(c.sum() / land_all), 3)
            totals.append(row)
        print(f"{y}: done", flush=True)
    data_dir = PAGE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    files = {"observed": f"hls-observed-{cell:g}deg.bin", "clear": f"hls-clear-{cell:g}deg.bin"}
    (data_dir / files["observed"]).write_bytes(obs_out.tobytes())
    (data_dir / files["clear"]).write_bytes(clear_out.tobytes())
    group = {"constellation": "Landsat + Sentinel-2", "key": "hls", "vendor": "HLS", "lazy": True, "cell": cell, "columns": cols_out,
             "div": DIV, "cells": np.diff(np.r_[0, keep]).astype(int).tolist(), "files": files, "totals": totals,
             "fetched_from": START, "first": START, "partial": None, "palette": PALETTE}
    updated = time.strftime("%-d %b %Y")
    data = {"tabs": [{"key": "hls", "vendor": "HLS", "palette": PALETTE, "groups": [group]}], "land": LAND.read_text().strip(),
            "updated": updated, "data_base": "data/", "source": str(SRC)}
    page = PAGE_DIR / "index.html"
    page.write_text(TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/")))
    (SITE / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>HLS</title>'
                                     '<meta http-equiv="refresh" content="0; url=archive_density/"><a href="archive_density/">HLS Archive Density</a>\n')
    (SITE / ".nojekyll").write_text("")
    print(f"{page}: {len(months)} months ({months[0]} to {months[-1]}), {len(keep)} land cells at {cell} deg; data "
          f"{sum((data_dir / x).stat().st_size for x in files.values()) / 1e6:.0f} MB", flush=True)
    return page


def publish(message: str = "HLS archive density") -> None:
    """_site -> the gh-pages branch of the repo, as one commit that replaces the last (no history of large data files)."""
    git = lambda *a: subprocess.run(["git", "-C", str(SITE), *a], check=True, capture_output=True, text=True).stdout
    if not (SITE / ".git").exists():
        git("init", "-q", "-b", "gh-pages")
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", message)
    git("reset", "-q", "--soft", git("rev-list", "--max-parents=0", "HEAD").split()[0]) if git("rev-list", "--count", "HEAD").strip() != "1" else None
    git("commit", "-q", "--amend", "--allow-empty", "-m", message)
    subprocess.run(["git", "-C", str(SITE), "push", "-q", "-f", REMOTE, "gh-pages"], check=True)
    print("pushed to gh-pages; live at https://pahbs.github.io/hls/archive_density/ after the Pages build", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "aggregate":
        for y in sys.argv[2:]:
            aggregate(int(y))
    elif sys.argv[1] == "build":
        build(float(sys.argv[2]) if len(sys.argv) > 2 else OUT_CELL)
    elif sys.argv[1] == "publish":
        publish(" ".join(sys.argv[2:]) or "HLS archive density")
