# HLS archive density

How often Harmonized Landsat and Sentinel-2 (HLS) observes the land, and how often it sees it clear, each month since
2013: https://pahbs.github.io/hls/archive_density/

The page is the CSDA archive density page (`pahbs/csda_summaries`, `lib/archive_density_template.html`) with HLS data:
Count = Observed days or Clear days, the mean over a cell's land pixels of the days in the month on which a pixel was
observed (or observed clear). Inputs, open questions and next steps: [PLAN.md](PLAN.md).

## Rebuild (on ADAPT)

1. Count the daily masks, a year per process, on forest nodes (about 50 min a year; years side by side):

       ssh forest202 /home/pmontesa/code/hls/archive_density/run_aggregate.sh 2025 2024 2023
       # logs: /explore/nobackup/people/pmontesa/hls_archive_density/logs/aggregate_<year>.log
       # store: /explore/nobackup/people/pmontesa/hls_archive_density/store/<year>.npz and ever_<year>.npy

2. Build the page and its data from every year in the store (a few minutes; needs ~10 GB of memory, so a forest node):

       ssh forest204 'cd /home/pmontesa/code/hls/archive_density && \
           /panfs/ccds02/app/modules/jupyter/ilab/tensorflow-kernel/bin/python hls_density.py build'
       # writes _site/archive_density/index.html and _site/archive_density/data/*.bin (not in git)

3. Publish: `python hls_density.py publish "message"` force-pushes `_site/` as a single commit to the `gh-pages` branch.
   GitHub Pages serves it (Settings > Pages > Deploy from a branch: `gh-pages`, `/ (root)`).

Code and template changes go to `master` as usual; the page data only ever live on `gh-pages`.
