"""
process.py — HYROX race data processor

Takes:
  - A Health Auto Export JSON file (Apple Watch data)
  - Hard-coded race metadata (athlete, race date, 16 segment splits, roxzone total)

Produces:
  - A processed JSON file with everything the Astro chart components need:
    HR samples, per-segment stats, zones, drift, recovery transitions,
    calories per segment, cadence buckets, pace buckets, race metadata.

How to run:
    python3 scripts/process.py

How to add a new race:
    1. Get the report card from the official HYROX results page
       (https://results.hyrox.com — find your bib).
    2. Get your Apple Watch data:
       - Open Health Auto Export app on your iPhone
       - Export Type: "Metrics"
       - Date range: just the race day
       - Format: JSON Aggregated
       - Email it to yourself or save to Files
    3. Update the constants block below (JSON_PATH, RACE_START_ISO,
       RACE_END_ISO, SPLITS, ROXZONE_TOTAL_SEC, RACE_META).
    4. Run this script — it writes the processed JSON to
       src/data/<race-id>.json where <race-id> is derived from the date.
    5. In your Astro race page, import the new JSON file. Every chart
       component renders the new race automatically.

Dependencies: standard library only. No pip install needed.
"""

import json
import os
from datetime import datetime

# =========================================================================
# CONFIGURE THIS BLOCK FOR YOUR RACE
# =========================================================================

# Path to the Health Auto Export JSON file
JSON_PATH = 'data/raw/HealthAutoExport-2026-04-12.json'

# Race start and end timestamps (must match a watch workout window with HR samples)
RACE_START_ISO = '2026-04-12 09:50:10 +0530'
RACE_END_ISO   = '2026-04-12 11:51:38 +0530'

# 16 segment splits in race order: (label, kind, duration "mm:ss", sublabel)
# Take these from the official HYROX results page.
SPLITS = [
    ('Run 1',             'run',     '07:01', '~1 km'),
    ('SkiErg',            'station', '05:11', '1000 m'),
    ('Run 2',             'run',     '06:40', '~1 km'),
    ('Sled Push',         'station', '05:26', '50 m'),
    ('Run 3',             'run',     '07:33', '~1 km'),
    ('Sled Pull',         'station', '10:01', '50 m'),
    ('Run 4',             'run',     '06:53', '~1 km'),
    ('Burpee Broad Jump', 'station', '08:37', '80 m'),
    ('Run 5',             'run',     '06:45', '~1 km'),
    ('Row',               'station', '05:49', '1000 m'),
    ('Run 6',             'run',     '05:44', '~1 km'),
    ('Farmers Carry',     'station', '02:29', '200 m'),
    ('Run 7',             'run',     '05:22', '~1 km'),
    ('Sandbag Lunges',    'station', '08:03', '100 m'),
    ('Run 8',             'run',     '08:02', '~1 km'),
    ('Wall Balls',        'station', '11:28', '100 reps'),
]

# Total roxzone time from the report card, in seconds (mm:ss converted)
ROXZONE_TOTAL_SEC = 612  # 10:12

# Race metadata used by article components (byline, page title, schema.org)
RACE_META = {
    'event': 'HYROX Bengaluru 2026',
    'date': '2026-04-12',
    'athlete': 'Prashant Singh',
    'bib': '95039',
    'age_group': '30-34',
    'final_time': '02:01:06',
    'tracker': 'Apple Watch',
}

# Where the processed JSON will be written (relative to repo root)
OUTPUT_PATH = 'src/data/race-2026-04-12.json'

# Heart rate zone reference. Set REF_MAX_HR to your best estimate of your max.
# Common methods:
#   - Use your observed race peak + 1 (assumes you got close to max in the race)
#   - 220 - age (rough; tends to underestimate for trained athletes)
#   - 208 - 0.7 * age (Tanaka; slightly better)
#   - Field-test from an all-out 4-min effort
REF_MAX_HR = 190

# =========================================================================
# END CONFIG BLOCK — you shouldn't need to edit below this line.
# =========================================================================

ZONES = [
    {'id': 1, 'label': 'Z1 Recovery',   'low_pct': 50, 'high_pct': 60,  'color': '#5C7593'},
    {'id': 2, 'label': 'Z2 Aerobic',    'low_pct': 60, 'high_pct': 70,  'color': '#5B8C7F'},
    {'id': 3, 'label': 'Z3 Tempo',      'low_pct': 70, 'high_pct': 80,  'color': '#C9A436'},
    {'id': 4, 'label': 'Z4 Threshold',  'low_pct': 80, 'high_pct': 90,  'color': '#D6783D'},
    {'id': 5, 'label': 'Z5 Anaerobic',  'low_pct': 90, 'high_pct': 100, 'color': '#D43F3F'},
]
for z in ZONES:
    z['low_bpm']  = z['low_pct']  * REF_MAX_HR / 100
    z['high_bpm'] = z['high_pct'] * REF_MAX_HR / 100

KJ_PER_KCAL = 4.184
GAP_THRESHOLD_SEC = 60       # gap larger than this is treated as missing data (sensor dropout)
BUCKET_SEC = 10              # cadence/speed bucket size
RECOVERY_WINDOW_SEC = 90     # HR samples captured after each station for recovery curve

def parse_dt(s):
    return datetime.strptime(s, '%Y-%m-%d %H:%M:%S %z')

def mmss(s):
    m, sec = s.split(':')
    return int(m) * 60 + int(sec)

def fmt_dur(sec):
    sec = int(round(sec))
    return f"{sec//60}:{sec%60:02d}"

def zone_for_hr(hr):
    if hr is None: return None
    if hr < ZONES[0]['low_bpm']: return 1
    if hr >= ZONES[-1]['high_bpm']: return 5
    for z in ZONES:
        if z['low_bpm'] <= hr < z['high_bpm']:
            return z['id']
    return 5

def main():
    if not os.path.exists(JSON_PATH):
        raise FileNotFoundError(
            f"Health Auto Export file not found at: {JSON_PATH}\n"
            f"Update JSON_PATH at the top of this script to point at your export.")

    with open(JSON_PATH) as f:
        raw = json.load(f)

    race_start = parse_dt(RACE_START_ISO)
    race_end   = parse_dt(RACE_END_ISO)

    metrics_by_name = {m['name']: m for m in raw['data']['metrics']}

    # --------- HR samples ---------
    hr_metric = metrics_by_name.get('heart_rate')
    if not hr_metric:
        raise KeyError("No 'heart_rate' metric found in the JSON. "
                       "Check your Health Auto Export 'Metrics' selection.")

    samples = []
    for s in hr_metric['data']:
        t = parse_dt(s['date'])
        if race_start <= t <= race_end:
            samples.append({
                't_sec': (t - race_start).total_seconds(),
                'avg': s['Avg'], 'min': s['Min'], 'max': s['Max'],
            })
    samples.sort(key=lambda x: x['t_sec'])
    if not samples:
        raise ValueError("No HR samples fell inside the race window. "
                         "Check RACE_START_ISO / RACE_END_ISO timestamps.")

    # --------- Segment timeline (insert equal roxzone gaps between segments) ---------
    n_transitions = len(SPLITS) - 1
    rz_each = ROXZONE_TOTAL_SEC / n_transitions
    segments = []
    cursor = 0.0
    for i, (label, kind, dur_str, sub) in enumerate(SPLITS):
        dur = mmss(dur_str)
        segments.append({
            'idx': i, 'label': label, 'kind': kind, 'sublabel': sub,
            'duration_s': dur, 'start_s': cursor, 'end_s': cursor + dur,
            'samples': [],
        })
        cursor += dur
        if i < len(SPLITS) - 1:
            segments.append({
                'idx': i, 'label': 'Roxzone', 'kind': 'roxzone',
                'sublabel': 'transition', 'duration_s': rz_each,
                'start_s': cursor, 'end_s': cursor + rz_each, 'samples': [],
            })
            cursor += rz_each
    total_s = cursor

    def bucket(t):
        for seg in segments:
            if seg['start_s'] <= t <= seg['end_s']:
                return seg
        return segments[-1] if t > segments[-1]['end_s'] else segments[0]

    for s in samples:
        bucket(s['t_sec'])['samples'].append(s)

    # --------- Per-segment HR stats ---------
    for seg in segments:
        if seg['samples']:
            avgs = [x['avg'] for x in seg['samples']]
            seg['avg_hr']  = sum(avgs) / len(avgs)
            seg['peak_hr'] = max(x['max'] for x in seg['samples'])
            seg['low_hr']  = min(x['min'] for x in seg['samples'])
            seg['zone']    = zone_for_hr(seg['avg_hr'])
            seg['pct_max'] = seg['avg_hr'] / REF_MAX_HR * 100
        else:
            seg['avg_hr'] = seg['peak_hr'] = seg['low_hr'] = seg['zone'] = seg['pct_max'] = None

    main_segments = [s for s in segments if s['kind'] != 'roxzone']

    # --------- Overall stats ---------
    overall_avg = sum(s['avg'] for s in samples) / len(samples)
    overall_peak = max(s['max'] for s in samples)
    overall_low = min(s['min'] for s in samples)
    overall_pct_max = overall_peak / REF_MAX_HR * 100

    # --------- Time in zones (gap-aware) ---------
    zone_seconds = {z['id']: 0.0 for z in ZONES}
    for i in range(len(samples) - 1):
        dt = samples[i+1]['t_sec'] - samples[i]['t_sec']
        if dt > GAP_THRESHOLD_SEC:
            continue
        z = zone_for_hr(samples[i]['avg'])
        if z is not None:
            zone_seconds[z] += dt
    total_zoned_s = sum(zone_seconds.values())
    zone_pct = {z: (s / total_zoned_s) * 100 if total_zoned_s else 0
                for z, s in zone_seconds.items()}
    threshold_plus_pct = zone_pct[4] + zone_pct[5]

    # --------- Drift halves ---------
    midpoint = total_s / 2
    fh = [s for s in samples if s['t_sec'] < midpoint]
    sh = [s for s in samples if s['t_sec'] >= midpoint]
    fh_avg = sum(s['avg'] for s in fh) / len(fh) if fh else 0
    sh_avg = sum(s['avg'] for s in sh) / len(sh) if sh else 0
    drift_overall = sh_avg - fh_avg

    runs_with_data = [s for s in main_segments if s['kind'] == 'run' and s['avg_hr'] is not None]
    stations_with_data = [s for s in main_segments if s['kind'] == 'station' and s['avg_hr'] is not None]
    def half_avg(lst):
        n = len(lst)
        if n < 2: return None, None
        h = n // 2
        early = sum(s['avg_hr'] for s in lst[:h]) / h
        late  = sum(s['avg_hr'] for s in lst[h:]) / (n - h)
        return early, late
    runs_early_avg, runs_late_avg = half_avg(runs_with_data)
    stations_early_avg, stations_late_avg = half_avg(stations_with_data)

    # --------- Recovery transitions ---------
    recoveries = []
    for i, seg in enumerate(segments):
        if (seg['kind'] == 'station'
                and i + 2 < len(segments)
                and segments[i+2]['kind'] == 'run'):
            next_run = segments[i+2]
            if seg['samples'] and next_run['samples']:
                station_end_hr = seg['samples'][-1]['avg']
                run_start_hr = next_run['samples'][0]['avg']
                recoveries.append({
                    'station': seg['label'],
                    'station_end_hr': station_end_hr,
                    'run_start_hr': run_start_hr,
                    'drop': station_end_hr - run_start_hr,
                    'station_end_t': seg['samples'][-1]['t_sec'],
                    'run_start_t': next_run['samples'][0]['t_sec'],
                })

    # --------- Calories per segment (from active_energy in kJ) ---------
    energy_metric = metrics_by_name.get('active_energy')
    if energy_metric:
        energy_samples = []
        for s in energy_metric['data']:
            t = parse_dt(s['date'])
            if race_start <= t <= race_end:
                energy_samples.append({
                    't_sec': (t - race_start).total_seconds(),
                    'kj': s['qty'],
                })
        energy_samples.sort(key=lambda x: x['t_sec'])
        for seg in segments:
            seg['kj'] = 0.0
        for e in energy_samples:
            bucket(e['t_sec'])['kj'] += e['kj']
        for seg in segments:
            seg['kcal'] = seg['kj'] / KJ_PER_KCAL
        total_kj = sum(e['kj'] for e in energy_samples)
        total_kcal = total_kj / KJ_PER_KCAL
    else:
        total_kj = total_kcal = 0
        for seg in segments:
            seg['kj'] = seg['kcal'] = 0

    # --------- Cadence buckets ---------
    step_metric = metrics_by_name.get('step_count')
    n_buckets = int(total_s / BUCKET_SEC) + 1
    step_buckets = [0.0] * n_buckets
    if step_metric:
        for s in step_metric['data']:
            t = parse_dt(s['date'])
            if race_start <= t <= race_end:
                t_sec = (t - race_start).total_seconds()
                idx = int(t_sec / BUCKET_SEC)
                if 0 <= idx < n_buckets:
                    step_buckets[idx] += s['qty']
    cadence_buckets = [
        {'t_sec': i * BUCKET_SEC, 'spm': s * 60 / BUCKET_SEC}
        for i, s in enumerate(step_buckets)
    ]

    for seg in segments:
        i1 = int(seg['start_s'] / BUCKET_SEC)
        i2 = min(int(seg['end_s'] / BUCKET_SEC) + 1, n_buckets)
        if i2 > i1:
            spms = [cadence_buckets[i]['spm'] for i in range(i1, i2)]
            seg['avg_spm']  = sum(spms) / len(spms)
            seg['peak_spm'] = max(spms)
        else:
            seg['avg_spm'] = seg['peak_spm'] = 0

    # --------- Speed / distance buckets ---------
    dist_metric = metrics_by_name.get('walking_running_distance')
    dist_buckets = [0.0] * n_buckets
    if dist_metric:
        for s in dist_metric['data']:
            t = parse_dt(s['date'])
            if race_start <= t <= race_end:
                t_sec = (t - race_start).total_seconds()
                idx = int(t_sec / BUCKET_SEC)
                if 0 <= idx < n_buckets:
                    dist_buckets[idx] += s['qty']
    speed_buckets = [
        {'t_sec': i * BUCKET_SEC, 'kmh': d * 3600 / BUCKET_SEC}
        for i, d in enumerate(dist_buckets)
    ]

    for seg in segments:
        i1 = int(seg['start_s'] / BUCKET_SEC)
        i2 = min(int(seg['end_s'] / BUCKET_SEC) + 1, n_buckets)
        dist_km = sum(dist_buckets[i1:i2]) if i2 > i1 else 0
        seg['dist_km'] = dist_km
        seg['pace_kmh'] = dist_km / (seg['duration_s'] / 3600) if dist_km > 0 else 0

    # --------- HR recovery windows ---------
    for r in recoveries:
        ws = r['station_end_t']
        we = ws + RECOVERY_WINDOW_SEC
        wsamps = [s for s in samples if ws <= s['t_sec'] <= we]
        r['recovery_window'] = [
            {'t_offset': s['t_sec'] - ws, 'hr': s['avg']} for s in wsamps
        ]

    # --------- Assemble output ---------
    out = {
        'samples': samples,
        'segments': segments,
        'main_segments': main_segments,
        'total_race_s': total_s,
        'overall': {
            'avg': overall_avg, 'peak': overall_peak, 'low': overall_low,
            'peak_pct': overall_pct_max,
        },
        'zones': ZONES,
        'zone_seconds': zone_seconds,
        'zone_pct': zone_pct,
        'threshold_plus_pct': threshold_plus_pct,
        'ref_max_hr': REF_MAX_HR,
        'drift': {
            'fh_avg': fh_avg, 'sh_avg': sh_avg, 'overall': drift_overall,
            'runs_early': runs_early_avg, 'runs_late': runs_late_avg,
            'stations_early': stations_early_avg, 'stations_late': stations_late_avg,
        },
        'recoveries': recoveries,
        'energy': {'total_kj': total_kj, 'total_kcal': total_kcal},
        'cadence_buckets': cadence_buckets,
        'speed_buckets': speed_buckets,
        'bucket_sec': BUCKET_SEC,
        'race_start_iso': RACE_START_ISO,
        'sample_count': len(samples),
        'race_meta': RACE_META,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(out, f, indent=2)

    # --------- Friendly summary printout ---------
    print(f"\n✓ Wrote {OUTPUT_PATH}")
    print(f"\nRace: {RACE_META['event']}")
    print(f"Athlete: {RACE_META['athlete']} (bib {RACE_META['bib']}, AG {RACE_META['age_group']})")
    print(f"Final time: {RACE_META['final_time']}")
    print(f"\nSamples: {len(samples)} HR samples, total race time: {fmt_dur(total_s)}")
    print(f"HR: avg={overall_avg:.1f}, peak={overall_peak} ({overall_pct_max:.0f}% max), low={overall_low}")
    print(f"\nZone distribution:")
    for z in ZONES:
        bar = '█' * int(zone_pct[z['id']] / 2)
        print(f"  {z['label']:18} {z['low_bpm']:>5.0f}-{z['high_bpm']:<5.0f}  "
              f"{fmt_dur(zone_seconds[z['id']]):>6}  {zone_pct[z['id']]:>5.1f}%  {bar}")
    print(f"Threshold+ (Z4+Z5): {threshold_plus_pct:.1f}%")
    if total_kcal:
        print(f"\nEnergy: {total_kcal:.0f} kcal total")

if __name__ == '__main__':
    main()
