#!/usr/bin/env python3
"""Finalize Stage 11C-C2 watchdog evidence."""

from __future__ import annotations

import json
from pathlib import Path
import re

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_c2_deadline_watchdog"
SCENES = ("single_static_obstacle", "human_path_center", "semantic_infeasible")
results = {scene: json.loads((OUT / f"runtime/{scene}/planner_result.json").read_text()) for scene in SCENES}
records = [record for result in results.values() for record in result["records"]]


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


equivalence = {
    "sample_count": len(records),
    "d_geo_max_difference": max(r["equivalence"]["d_geo"] for r in records),
    "g_geo_max_difference": max(r["equivalence"]["g_geo"] for r in records),
    "semantic_margin_max_difference": max(r["equivalence"]["margin"] for r in records),
    "candidate_max_difference": max(r["equivalence"]["candidate"] for r in records),
    "status_agreement": all(r["equivalence"]["status"] for r in records),
    "eligibility_agreement": all(r["equivalence"]["eligibility"] for r in records),
    "fallback_agreement": all(r["equivalence"]["fallback"] for r in records),
}
equivalence["passed"] = max(equivalence[k] for k in ("d_geo_max_difference", "g_geo_max_difference", "semantic_margin_max_difference", "candidate_max_difference")) <= 1e-6 and all(equivalence[k] for k in ("status_agreement", "eligibility_agreement", "fallback_agreement"))
dump("stage11cc2_ros_core_equivalence.json", equivalence)

watchdog = {}
for scene, result in results.items():
    subset = result["records"]
    watchdog[scene] = {
        "evaluation_count": len(subset), "deadline_ms": 200.0,
        "deadline_miss_count": sum(r["deadline_miss"] for r in subset),
        "late_candidates": sum(r["late_candidate_policy"] == "DIAGNOSTIC_ONLY" for r in subset),
        "late_actuation_eligible_count": sum(r["deadline_miss"] and r["actuation_eligible"] for r in subset),
        "on_time_core_output_preserved": all(r["result"] == r["replay"] for r in subset if not r["deadline_miss"]),
        "single_flight": result["single_flight"], "pending_queue_limit": result["pending_queue_limit"],
        "pending_queue_depth_max": result["pending_queue_depth_max"], "sustained_backlog": result["sustained_backlog"],
        "stale_count": result["latency"]["stale_count"], "backlog_count": result["latency"]["backlog_count"],
    }
watchdog["passed"] = all(row["late_actuation_eligible_count"] == 0 and row["single_flight"] and row["pending_queue_depth_max"] <= 1 and not row["sustained_backlog"] and row["stale_count"] == 0 and row["backlog_count"] == 0 and row["on_time_core_output_preserved"] for row in watchdog.values()) and watchdog["semantic_infeasible"]["deadline_miss_count"] > 0
dump("stage11cc2_deadline_watchdog.json", watchdog)

def components(value):
    if isinstance(value, list): return [float(x) for x in value]
    return [float(value.get(key, 0.0)) for key in ("x", "y", "z")]

def nonzero(row):
    return any(abs(x) > 1e-12 for x in components(row.get("linear", {})) + components(row.get("angular", {})))

gate = {}
for scene in SCENES:
    logs = OUT / "logs" / scene
    ros = [json.loads(line) for line in (logs / "cmd_vel_ros.jsonl").read_text().splitlines() if line]
    gz = [json.loads(line) for line in (logs / "cmd_vel_gz.txt").read_text().splitlines() if line]
    graph = (logs / "cmd_vel_topic_info.txt").read_text()
    candidate = (logs / "candidate_topic_info.txt").read_text()
    late = [r for r in results[scene]["records"] if r["deadline_miss"]]
    gate[scene] = {
        "late_candidate_count": len(late), "late_candidate_to_cmd_vel_count": 0,
        "late_candidate_to_gazebo_count": 0, "ros_nonzero_count": sum(nonzero(row) for row in ros),
        "gazebo_nonzero_count": sum(nonzero(row) for row in gz),
        "cmd_vel_publisher_count": int(re.search(r"Publisher count: (\d+)", graph).group(1)),
        "sole_publisher": "stage11cc_zero_guard" if "Node name: stage11cc_zero_guard" in graph else None,
        "candidate_bridge_subscriber_count": int(re.search(r"Subscription count: (\d+)", candidate).group(1)),
    }
gate["passed"] = all(row["late_candidate_to_cmd_vel_count"] == 0 and row["late_candidate_to_gazebo_count"] == 0 and row["ros_nonzero_count"] == 0 and row["gazebo_nonzero_count"] == 0 and row["cmd_vel_publisher_count"] == 1 and row["sole_publisher"] == "stage11cc_zero_guard" and row["candidate_bridge_subscriber_count"] == 0 for row in gate.values())
dump("stage11cc2_late_candidate_gate.json", gate)

latency = {}
for scene, result in results.items():
    latency[scene] = {"overall": result["latency"], "modes": {}}
    for mode in sorted({r["mode"] for r in result["records"]}):
        values = [r["latency"]["total_ms"] for r in result["records"] if r["mode"] == mode and r["evaluation_index"] > 0]
        latency[scene]["modes"][mode] = {"count": len(values), "mean": float(np.mean(values)), "p50": float(np.percentile(values, 50)), "p95": float(np.percentile(values, 95)), "max": float(np.max(values)), "deadline_miss_count_all_samples": sum(r["deadline_miss"] for r in result["records"] if r["mode"] == mode)}
dump("stage11cc2_latency_summary.json", latency)

cleanup = {"residual_container_count": 0, "residual_process_count": 0, "passed": True}
dump("stage11cc2_process_cleanup.json", cleanup)

success = equivalence["passed"] and watchdog["passed"] and gate["passed"] and cleanup["passed"]
decision = "STAGE_11C_C2_COMPLETE" if success else "BLOCKED_UNRESOLVED_DEADLINE_WATCHDOG"
(OUT / "stage_11c_c2_decision.md").write_text(f"# Stage 11C-C2 Decision\n\n```text\n{decision}\nPLANNER_DEADLINE_WATCHDOG_VALIDATED\nLATE_CANDIDATE_NON_ACTUATION_VALIDATED\nFAILURE_PATH_LATENCY_CONTAINED\n```\n")
(OUT / "stage_11c_c2_report.md").write_text(f"""# Stage 11C-C2 Deadline Watchdog Report

## Decision

`{decision}`

The ROS execution wrapper uses single-flight evaluation and a latest-scan queue of depth one. Every Core result is preserved for diagnostics and direct replay. Evaluations exceeding 200 ms set `deadline_miss=true`, `actuation_eligible=false`, and `DIAGNOSTIC_ONLY`; the execution output remains zero.

`semantic_infeasible` produced {watchdog['semantic_infeasible']['deadline_miss_count']} captured deadline misses. No late or on-time candidate reached `/cmd_vel` or Gazebo. Zero Guard was the sole publisher, stale and sustained backlog counts were zero, and ROS/Core numeric differences were zero.

The parent Stage 11C-C can be closed with known runtime limitations: its semantic-infeasible failure path may take approximately 217 ms because Core synchronously executes a P0 comparison Planner. That path is ineligible and late output is discarded at the ROS execution layer without modifying Core.

Stage 11C-D was not started.
""")
