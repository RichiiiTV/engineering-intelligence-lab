# M5 reproducible scorecard

Gate: FAIL / INCOMPLETE; unrun slots: 0.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| ollama | single | other-station | completed | pass | 7667 | - | 18.391000000061467 | unknown |
| ollama | single | other-station | completed | citations | 18095 | - | 36.79700000002049 | unknown |
| ollama | single | no-increase | completed | citations | 12250 | - | 23.219000000040978 | unknown |
| ollama | single | no-increase | completed | citations | 12085 | - | 23.31299999996554 | unknown |
| ollama | single | conflicting-records | completed | pass | 8539 | - | 21.875 | unknown |
| ollama | single | conflicting-records | completed | pass | 8475 | - | 21.594000000040978 | unknown |
| ollama | single | missing-document | completed | pass | 5515 | - | 13.905999999959022 | unknown |
| ollama | single | missing-document | completed | pass | 5584 | - | 15.65700000000652 | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| ollama | single | 5 / 8 | 21.735 | 9776.2 | fail; do not rank performance |
