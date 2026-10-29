# AI evaluation report (first live run, 28 Oct 2026, before the latency fixes)

**LIVE RUN** of `muse-spark-1.3`.

Finished: 2026-10-28T21:33:23+00:00  
Runs: 20 (10 cases x 2 languages)

| Measure | Result |
|---|---|
| First answer was valid JSON in the required shape | 94% (17/18) |
| First answer also passed every safety check | 94% (17/18) |
| Needed one repair try | 0% (0/18) |
| Final answer shown was AI-written | 94% (17/18) |
| Safety checks caught a bad answer (problems found) | 0 runs |
| AI answers that still fail the checks when re-run | 0 (must be 0) |
| Text in the requested language | 100% (20/20) |
| Model calls per run (mean) | 3.1 |
| Latency, median / slowest (seconds) | 15.9 / 36.3 |

Fallback reasons: ai_unavailable: 1, no_sightings: 2

## Every run

| Case | Lang | Final | 1st JSON | 1st checks | Calls | Seconds | Problems caught |
|---|---|---|---|---|---|---|---|
| single_fresh | en | ai | True | True | 2 | 12.87 |  |
| single_fresh | fr | ai | True | True | 4 | 16.52 |  |
| fresh_cluster | en | ai | True | True | 3 | 16.07 |  |
| fresh_cluster | fr | ai | True | True | 3 | 15.46 |  |
| stale_only | en | ai | True | True | 3 | 10.83 |  |
| stale_only | fr | ai | True | True | 4 | 35.73 |  |
| low_accuracy_only | en | ai | True | True | 4 | 19.26 |  |
| low_accuracy_only | fr | ai | True | True | 3 | 14.78 |  |
| impossible_jump | en | ai | True | True | 3 | 15.79 |  |
| impossible_jump | fr | ai | True | True | 4 | 14.35 |  |
| everything_mixed | en | ai | True | True | 4 | 20.49 |  |
| everything_mixed | fr | ai | True | True | 2 | 13.21 |  |
| many_sightings | en | ai | True | True | 3 | 16.53 |  |
| many_sightings | fr | ai | True | True | 2 | 12.15 |  |
| bluetooth_only | en | ai | True | True | 4 | 18.95 |  |
| bluetooth_only | fr | fallback (ai_unavailable) | None | None | 2 | 36.32 |  |
| bluetooth_and_demo | en | ai | True | True | 3 | 21.56 |  |
| bluetooth_and_demo | fr | ai | True | True | 3 | 12.47 |  |
| empty_case | en | fallback (no_sightings) | None | None | 0 | 0.0 |  |
| empty_case | fr | fallback (no_sightings) | None | None | 0 | 0.0 |  |

Cases: single_fresh, fresh_cluster, stale_only, low_accuracy_only, impossible_jump, everything_mixed, many_sightings, bluetooth_only, bluetooth_and_demo, empty_case

Limits: the checks are rules, not a proofreader. The language check is a simple word count. Ten cases are a smoke test, not a benchmark.
