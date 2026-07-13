# Stage 10C Decision

```text
BLOCKED_OPTIMIZATION_CONVERGENCE
```

Metric identity and direct-logits sanity pass perfectly. Residuals are not limited
to boundaries or the ROBOT antenna. The one selected fix—raising the frozen
single-image optimization budget from 80 to a finite 1,200 steps while retaining
the same model and weighted CE—passes the loss-ratio target but fails all-pixel
accuracy, macro F1, HUMAN recall, and ROBOT recall requirements. Class recalls
remain unstable late in training. No additional fix or recheck is permitted.
