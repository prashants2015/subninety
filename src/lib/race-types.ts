/**
 * race-types.ts
 *
 * Shared TypeScript interfaces for the HYROX race data structure.
 * Every chart component imports from this file so the data shape is
 * defined in exactly one place.
 *
 * If process.py adds a new field, add it here too — then TypeScript
 * will surface every component that needs to be updated.
 */

export interface HRSample {
  /** Seconds elapsed since race_start_iso */
  t_sec: number;
  /** Average heart rate in this sample window (bpm) */
  avg: number;
  /** Minimum heart rate in this sample window (bpm) */
  min: number;
  /** Maximum heart rate in this sample window (bpm) */
  max: number;
}

export interface Zone {
  id: 1 | 2 | 3 | 4 | 5;
  label: string; // e.g. "Z4 Threshold"
  low_pct: number; // e.g. 80
  high_pct: number; // e.g. 90
  low_bpm: number; // e.g. 152
  high_bpm: number; // e.g. 171
  color: string; // e.g. "#D6783D"
}

export type SegmentKind = "run" | "station" | "roxzone";

export interface Segment {
  idx: number;
  label: string; // e.g. "Sled Pull"
  kind: SegmentKind;
  sublabel: string; // e.g. "50 m"
  duration_s: number;
  start_s: number; // race-relative seconds
  end_s: number;
  samples: HRSample[]; // HR samples that fell inside this segment

  // Derived per-segment HR stats — null when the segment has no samples (e.g. SkiErg sensor gap)
  avg_hr: number | null;
  peak_hr: number | null;
  low_hr: number | null;
  zone: 1 | 2 | 3 | 4 | 5 | null;
  pct_max: number | null;

  // Movement & energy metrics (added by process.py v3+)
  kj: number; // energy in kilojoules
  kcal: number; // energy in kilocalories
  avg_spm: number; // avg cadence (steps per minute)
  peak_spm: number;
  dist_km: number; // distance covered in segment
  pace_kmh: number; // average pace
}

export interface RecoveryTransition {
  station: string;
  station_end_hr: number;
  run_start_hr: number;
  drop: number; // station_end_hr - run_start_hr (positive = HR dropped)
  station_end_t: number;
  run_start_t: number;
  recovery_window: { t_offset: number; hr: number }[];
}

export interface RaceData {
  samples: HRSample[];
  segments: Segment[]; // all 31 entries: 16 main + 15 roxzones
  main_segments: Segment[]; // just the 16 main segments
  total_race_s: number;

  overall: {
    avg: number;
    peak: number;
    low: number;
    peak_pct: number; // peak as % of ref_max_hr
  };

  zones: Zone[];
  zone_seconds: Record<string, number>; // key is zone id as string ("1".."5")
  zone_pct: Record<string, number>;
  threshold_plus_pct: number; // % time in Z4 + Z5
  ref_max_hr: number; // e.g. 190

  drift: {
    fh_avg: number;
    sh_avg: number;
    overall: number;
    runs_early: number;
    runs_late: number;
    stations_early: number;
    stations_late: number;
  };

  recoveries: RecoveryTransition[];

  energy: {
    total_kj: number;
    total_kcal: number;
  };

  cadence_buckets: { t_sec: number; spm: number }[];
  speed_buckets: { t_sec: number; kmh: number }[];
  bucket_sec: number; // typically 10

  race_start_iso: string;
  sample_count: number;

  race_meta: {
    event: string;
    date: string;
    athlete: string;
    bib: string;
    age_group: string;
    final_time: string;
    tracker: string;
  };
}
