# HLS archive density: plan

A page that shows where and how often HLS observes the land surface, and how often those observations are clear,
2013-2025. Built from daily global masks, on the page template of the CSDA archive density page
(`pahbs/csda_summaries`: `lib/archive_density_template.html`, `lib/archive_density.py`).

## Inputs (checked 2026-11-19)

| | `daily_masks` | `daily_clear_masks` |
|---|---|---|
| Path | `/panfs/ccds02/nobackup/projects/hls/HLS/qzhou2/Cloudprob/Revisit_all/Mosaic/revisit_ts/Global/daily_masks/<year>/mask_<YYYYDDD>.tif` | same, `daily_clear_masks/` |
| Meaning | 1 = an HLS observation that day | 1 = a clear observation that day |
| Years | 2013-2025 (2013 from day 101, Landsat 8) | 2013-2025 **except 2018 and 2021** |
| Size | 30 GB | 31 GB |

Every file: one band, uint8, values 0 / 1, LZW, tiled; 40,149 x 16,979 pixels, EPSG:4326, about 0.009 deg (~1 km),
lon -180 to 180, lat -69.5 to 83.7. One day of both masks reads in ~2 s on a forest node.

Not what the first plan assumed: these are **daily 0/1 masks, not counts**, and they are **Landsat and Sentinel-2
together** (no L30 / S30 split in these files). Counts come from adding days up.

### Questions
1. **L30 / S30 separately**: are there separate masks per sensor? The neighbouring folders (`Mosaic/<year>`,
   `ts-revisit-<year>`, `Climatology_2014_2025`, the regional `*_daily_masks`, `Countries`) are not readable to us:
   group read access would let us check.
2. **Clear masks for 2018 and 2021** are missing.
3. **Observation masks empty from the equator to ~1° N** (checked 2026-11-19, days 183 of 2013, 2017, 2020, 2024 and
   day 15 of 2024): pixel rows from 0° to about 1° N are 0.0-1.5% observed, against 6-10% just north and south, in
   every year, while the clear masks are normal there (so many more pixels are "clear" than "observed" in that band:
   this is the 0.07% of clear-but-not-observed pixels first seen on 2020-183). Looks like the mosaic step dropped the
   band from the observation masks. Can they be regenerated? Until then the page counts a pixel observed if either mask
   has it, so observed days read low in the band (cloudy-only observations are lost), and near zero in 2018 and 2021.
4. Nodata: the clear masks declare 255 but have none (0 = not clear or not observed); the observation masks declare none.
5. `World_Countries_noAntarctica_binary_aligned_to_template.tif` (a land mask on this grid) is not readable to us. Until
   it is, the area counted is every pixel HLS observed at least once.

## What the page shows

Same layout as the CSDA density page: a global map, a monthly timeline with Play, summary tiles, a month table, the
interactive globe option, light and dark themes.

- **Count**: Observed days, or Clear days. A cell's value is the mean number of days in the month on which a pixel in
  the cell was observed (or observed clear), 0-31. This is the template's "Days with an acquisition" view, which fits.
- **View**: This month, or a per-year mean (replaces "running total", which has no meaning for days).
- **Timeline**: one bar per month, the land-mean observed days; above the active bar "X.X observed days (Y.Y clear)",
  hover "X.X observed days in / Jun 2020, Y.Y clear".
- **Tiles**: mean revisit this month (days between observations), share of land observed at least once this month, share
  of observed days that were clear, best-observed month.
- **Later**: Daily view of the selected month (a day at a time, share of each cell observed that day); summary maps
  over the whole record (median gap between clear observations, share of weeks with a clear look); L30 / S30 tabs if
  separate masks exist.

## Steps

1. **Aggregate** (`archive_density/hls_density.py aggregate --year YYYY`, one process per year on forest202-205): read
   each day's two masks and count, per 0.1 deg cell, the observed and the clear pixels (at most 121 pixels a cell, so
   uint8). Saved per year as `<store>/<year>.npz`: `obs[day, cell]`, `clear[day, cell]`, and the pixel count per cell,
   only for cells HLS ever observed (~1.5 M). About 0.5 GB a year, 7 GB in all, under
   `/explore/nobackup/projects/hls/...` or `/explore/nobackup/people/pmontesa/hls_archive_density/`. Days with a
   missing file are recorded as missing, not as zero. Estimated 2-3 h of reading in all, under 1 h split across nodes.
2. **Check**: one month against the source rasters directly (a few cells, by hand); a map of the year's mean against
   the our coverage results (`coverage_results_latbin_*` CSVs in the same folder).
3. **Monthly frames** (`build`): from the 0.1 deg store, mean observed / clear days per cell and month at 0.25 deg (the
   0.1 deg store can be summed to any coarser grid). Stored as binary, one byte per land cell per month (days in
   tenths would need two), one file per metric: ~250 k cells x 156 months = ~40 MB raw, ~10 MB compressed per metric.
4. **Page** (`archive_density/template.html`, forked from the CSDA template): vendor tabs and commercial switches
   removed; the Count / View selectors above; a sequential single-hue scale for days (0-31) checked with the dataviz
   palette validator in light and dark; binary frame loading instead of the delta-encoded JSON.
5. **Publish**: the page and its data on this repo's GitHub Pages from a `gh-pages` branch replaced by a single commit on
   each publish (no history pile-up, as with `csda_summaries_data`). Link from the CSDA density page.

## Repo layout (`hls/archive_density/`)

    PLAN.md            this file
    README.md          what the page shows, how to rebuild
    hls_density.py     aggregate (rasters -> per-year store), build (store -> page + data), publish
    template.html      the page template
    LOG.md             newest first
