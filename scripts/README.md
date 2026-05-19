![scripts-README](scripts-README_2.md)# scripts/

Python scripts for processing race data into the JSON files that the Astro
chart components consume.

## process.py

Takes a Health Auto Export JSON (Apple Watch data) and the official HYROX
report card splits, produces a single processed JSON that every chart
component on the site uses.

### Run it

```bash
python3 scripts/process.py
```

No `pip install` needed — uses only the Python standard library.

### Add a new race

Open `process.py` and update the **CONFIGURE THIS BLOCK** section near the top:

1. **JSON_PATH** — point at your new Health Auto Export file (drop it under `data/raw/` for organisation)
2. **RACE_START_ISO / RACE_END_ISO** — start and end timestamps of the race
3. **SPLITS** — the 16 segment times from your official HYROX report card
4. **ROXZONE_TOTAL_SEC** — total roxzone time from the report card (in seconds)
5. **RACE_META** — athlete name, bib, age group, etc.
6. **OUTPUT_PATH** — where the processed JSON should land (typically `src/data/race-YYYY-MM-DD.json`)
7. **REF_MAX_HR** — your max heart rate reference for zone calculations

Then run the script. It writes the JSON to `src/data/`, where your Astro page
can import it.

### Get the Health Auto Export file

1. Install **Health Auto Export** on iPhone (paid app, ~$2 one-time or free trial)
2. Open the app → **Export Data**
3. Pick **Metrics** (not Workouts — we don't need the workout route data)
4. **Date Range**: the race day
5. **Aggregation**: leave as default (will give per-sample resolution for HR)
6. **Format**: JSON Aggregated
7. **Metrics to include** (minimum):
   - Heart rate
   - Step count
   - Walking + running distance
   - Active energy
   - Optionally: physical effort, respiratory rate (sparse but interesting)
8. Email the JSON to yourself or save to Files

### Output

`process.py` writes a single JSON containing:

- `samples` — every HR sample inside the race window
- `segments` — 31 entries (16 main + 15 roxzones) with timing + per-segment stats
- `main_segments` — just the 16 main segments
- `overall` — avg / peak / low / peak% across the race
- `zones` — Z1–Z5 definitions
- `zone_seconds` / `zone_pct` — time spent in each zone
- `drift` — first-half vs second-half averages, broken out by segment type
- `recoveries` — HR transition from each station's end into the next run
- `energy` — total kJ and kcal burned
- `cadence_buckets` / `speed_buckets` — 10-second windows of steps/min and km/h
- `race_meta` — bib, age group, finish time, etc.

This is the file every chart component on the site reads from.
