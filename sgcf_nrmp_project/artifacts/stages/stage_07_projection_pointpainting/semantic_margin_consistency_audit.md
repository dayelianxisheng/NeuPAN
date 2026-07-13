# Semantic Margin Mathematical Consistency Audit

## Finding

The reported `0.4146 m` maximum was an implementation error, not an intentional semantic-margin definition. Configuration inspection found no margin above HUMAN `0.35 m` and no unit conversion or override.

Before repair, `d_geo` was the rectangle-to-current-LiDAR-point distance, while each `d_j` was rectangle-to-complete-semantic-polygon distance. The polygon list included surfaces not represented by the current nearest-hit LiDAR scan and could include occluded instances. Although pose and footprint matched, the obstacle carrier and visibility set did not. The excess therefore mixed semantic margin with point-cloud sparsity/full-surface differences and risked complete-world leakage.

## Repair

Both terms now use the same current observable LiDAR point set and the same batched rectangle-to-point formula:

```text
d_geo = min_i distance(footprint(q), observable_point_i)
d_eff = min_i [distance(footprint(q), observable_point_i) - visible_margin_i]
m_sem = max(0, d_geo - d_eff)
```

All observable points remain in `d_geo`. A semantic margin is assigned only to points with valid projection/reliable semantic labels; UNKNOWN, invalid, occluded, or out-of-FOV semantics receive zero margin. No world polygon enters the online labeler.

Runtime assertions enforce `m_sem >= -1e-9` and `m_sem <= max_visible_class_margin + 1e-9`. The configured engineering tolerance for acceptance is `1e-6 m`.

## Result

- Pre-repair maximum: 0.414615 m.
- Post-repair maximum: 0.3500000000000001 m.
- Configured visible maximum: 0.35 m.
- Violations above `0.350001 m`: 0.
- Ten required boundary/information tests: passed.

The mathematical definition is unchanged; the implementation now uses the required common observable geometry domain.
