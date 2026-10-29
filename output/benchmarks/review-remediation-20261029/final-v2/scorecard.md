# M5 reproducible scorecard

Gate: PASS; unrun slots: 0.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| ollama | single | other-station | completed | pass | 17433 | - | 30.45299999997951 | unknown |
| ollama | single | other-station | completed | pass | 7606 | - | 19.54700000002049 | unknown |
| ollama | single | no-increase | completed | pass | 12561 | - | 24.43700000003446 | unknown |
| ollama | single | no-increase | completed | pass | 12344 | - | 24.859000000054948 | unknown |
| ollama | single | conflicting-records | completed | pass | 8514 | - | 21.468999999924563 | unknown |
| ollama | single | conflicting-records | completed | pass | 8439 | - | 20.32900000002701 | unknown |
| ollama | single | missing-document | completed | pass | 5559 | - | 14.655999999959022 | unknown |
| ollama | single | missing-document | completed | pass | 5558 | - | 14.672000000020489 | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| ollama | single | 8 / 8 | 20.899 | 9751.8 | pass |
