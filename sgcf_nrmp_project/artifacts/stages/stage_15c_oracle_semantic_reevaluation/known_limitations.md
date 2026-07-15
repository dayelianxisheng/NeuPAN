# Known Limitations

- Oracle semantics are simulation ground truth and are not Stage 10 prediction.
- HUMAN and mixed P2 runs were safely rejected at the frozen maximum HUMAN margin.
- Deadline misses occurred only on diagnostic/ineligible paths and were isolated by the watchdog.
- Clearance increases from rejected or stationary P2 runs do not demonstrate semantic navigation benefit.
- The offline class-clearance evaluator uses frozen world primitives for scoring only; world geometry never enters the online Exact Geometry checker.
- No dynamic-target prediction or formal safety guarantee is provided.
