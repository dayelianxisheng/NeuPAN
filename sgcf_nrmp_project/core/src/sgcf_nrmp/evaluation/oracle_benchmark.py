"""Latency summary helpers for neural and exact-geometry queries."""

from __future__ import annotations

import numpy as np


def latency_summary(milliseconds: list[float], query_count: int) -> dict[str,float]:
    values=np.asarray(milliseconds,dtype=np.float64)
    return {"mean_ms":float(values.mean()),"p50_ms":float(np.quantile(values,.5)),"p95_ms":float(np.quantile(values,.95)),"per_query_mean_ms":float(values.mean()/query_count),"repeats":int(len(values)),"query_count":int(query_count)}
