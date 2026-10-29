# AI evaluation report

**LIVE RUN** of `muse-spark-1.3`.

Percentages count only runs where the model gave a first answer.

Finished: 2026-10-29T18:34:31+00:00  
Runs: 20 (10 cases x 2 languages)

| Measure | Result |
|---|---|
| First answer was valid JSON in the required shape | 100% (18/18) |
| First answer also passed every safety check | 100% (18/18) |
| Needed one repair try | 0% (0/18) |
| Final answer shown was AI-written | 100% (18/18) |
| Model did not answer (timeout or error), fixed wording shown | 0 runs |
| Safety checks caught a bad answer (problems found) | 0 runs |
| AI answers that still fail the checks when re-run | 0 (must be 0) |
| Text in the requested language | 100% (20/20) |
| Model calls per run (mean) | 2.0 |
| Latency, median / slowest (seconds) | 12.2 / 79.5 |

Fallback reasons: no_sightings: 2

## Every run

| Case | Lang | Final | 1st JSON | 1st checks | Calls | Seconds | Problems caught |
|---|---|---|---|---|---|---|---|
| single_fresh | en | ai | True | True | 2 | 22.17 |  |
| single_fresh | fr | ai | True | True | 2 | 34.51 |  |
| fresh_cluster | en | ai | True | True | 2 | 79.5 |  |
| fresh_cluster | fr | ai | True | True | 2 | 10.54 |  |
| stale_only | en | ai | True | True | 2 | 11.45 |  |
| stale_only | fr | ai | True | True | 2 | 9.79 |  |
| low_accuracy_only | en | ai | True | True | 2 | 12.3 |  |
| low_accuracy_only | fr | ai | True | True | 2 | 9.7 |  |
| impossible_jump | en | ai | True | True | 2 | 10.22 |  |
| impossible_jump | fr | ai | True | True | 2 | 8.6 |  |
| everything_mixed | en | ai | True | True | 2 | 16.69 |  |
| everything_mixed | fr | ai | True | True | 2 | 15.0 |  |
| many_sightings | en | ai | True | True | 2 | 13.99 |  |
| many_sightings | fr | ai | True | True | 2 | 16.1 |  |
| bluetooth_only | en | ai | True | True | 2 | 18.62 |  |
| bluetooth_only | fr | ai | True | True | 2 | 12.15 |  |
| bluetooth_and_demo | en | ai | True | True | 2 | 11.0 |  |
| bluetooth_and_demo | fr | ai | True | True | 2 | 12.17 |  |
| empty_case | en | fallback (no_sightings) | None | None | 0 | 0.0 |  |
| empty_case | fr | fallback (no_sightings) | None | None | 0 | 0.0 |  |

Cases: single_fresh, fresh_cluster, stale_only, low_accuracy_only, impossible_jump, everything_mixed, many_sightings, bluetooth_only, bluetooth_and_demo, empty_case

Limits: the checks are rules, not a proofreader. The language check is a simple word count. Ten cases are a smoke test, not a benchmark.
