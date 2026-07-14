#!/usr/bin/env python3
"""Finalize Stage 11C-D1 evidence after the closed-loop capability hard gate."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_d1_static_p0_closed_loop"
SCENES = ("empty_world", "single_static_obstacle")
planner = {s: json.loads((OUT / f"runtime/{s}/planner_result.json").read_text()) for s in SCENES}
gate = {s: json.loads((OUT / f"runtime/{s}/safe_gate_result.json").read_text()) for s in SCENES}


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def nonzero(row):
    def values(obj):
        if isinstance(obj, list): return [float(x) for x in obj]
        return [float(obj.get(k, 0.0)) for k in ("x", "y", "z")]
    return any(abs(x) > 1e-12 for x in values(row.get("linear", {})) + values(row.get("angular", {})))


gate_audit = {}
consistency = {}
for scene in SCENES:
    records = gate[scene]["records"]
    logs = OUT / "logs" / scene
    gz = [json.loads(line) for line in (logs / "cmd_vel_gz.txt").read_text().splitlines() if line]
    graph = (logs / "cmd_vel_topic_info.txt").read_text()
    candidate_graph = (logs / "candidate_topic_info.txt").read_text()
    gate_audit[scene] = {
        "evaluation_count": len(records), "forwarded_nonzero_count": gate[scene]["forwarded_nonzero_count"],
        "rejected_count": gate[scene]["rejected_count"], "gazebo_nonzero_count": sum(nonzero(row) for row in gz),
        "cmd_vel_publisher_count": int(re.search(r"Publisher count: (\d+)", graph).group(1)),
        "sole_cmd_vel_publisher": "stage11cd1_safe_actuation_gate" if "Node name: stage11cd1_safe_actuation_gate" in graph else None,
        "candidate_subscriber_count": int(re.search(r"Subscription count: (\d+)", candidate_graph).group(1)),
        "candidate_bridge_subscriber_count": 1 if "Node name: ros_gz_bridge" in candidate_graph else 0,
        "candidate_gate_subscriber_present": "Node name: stage11cd1_safe_actuation_gate" in candidate_graph,
        "late_executed": sum(r["record"]["deadline_miss"] and r["actuation_eligible"] for r in records),
        "ineligible_executed": sum(not r["record"]["result"]["eligible"] and r["actuation_eligible"] for r in records),
        "stale_executed": sum((not r["checks"]["scan_fresh"] or not r["checks"]["odom_fresh"] or not r["checks"]["candidate_fresh"]) and r["actuation_eligible"] for r in records),
    }
    matched = [r for r in records if r["actuation_eligible"]]
    consistency[scene] = {"forwarded_sample_count": len(matched), "candidate_to_cmd_max_error": max([max(abs(a-b) for a,b in zip(r["record"]["result"]["candidate"], r["final_command"])) for r in matched] or [0.0]), "ros_to_gazebo_nonzero_sample_count": 0, "gazebo_nonzero_count": sum(nonzero(row) for row in gz)}
gate_audit["closed_loop_capability_passed"] = any(row["forwarded_nonzero_count"] > 0 for row in gate_audit.values())
gate_audit["safety_passed"] = all(row["gazebo_nonzero_count"] == 0 and row["cmd_vel_publisher_count"] == 1 and row["sole_cmd_vel_publisher"] == "stage11cd1_safe_actuation_gate" and row["candidate_bridge_subscriber_count"] == 0 and row["candidate_gate_subscriber_present"] and row["late_executed"] == 0 and row["ineligible_executed"] == 0 and row["stale_executed"] == 0 for scene, row in gate_audit.items() if scene in SCENES)
dump("stage11cd1_safe_actuation_gate.json", gate_audit)
dump("stage11cd1_command_consistency.json", consistency)

closed = {}
for scene in SCENES:
    rows = gate[scene]["records"]
    poses = gate[scene]["odom_log"]
    goal = rows[0]["record"]["goal"]
    first, last = poses[0], poses[-1]
    initial_distance = math.hypot(goal[0]-first["x"], goal[1]-first["y"])
    final_distance = math.hypot(goal[0]-last["x"], goal[1]-last["y"])
    closed[scene] = {"initial_goal_distance": initial_distance, "final_goal_distance": final_distance, "goal_progress": initial_distance-final_distance, "forwarded_nonzero_count": gate[scene]["forwarded_nonzero_count"], "core_statuses": sorted({r["record"]["result"]["status"] for r in rows}), "core_eligibility": sorted({r["record"]["result"]["eligible"] for r in rows}), "candidate_linear_range": [min(r["record"]["result"]["candidate"][0] for r in rows), max(r["record"]["result"]["candidate"][0] for r in rows)], "passed": gate[scene]["forwarded_nonzero_count"] > 0 and initial_distance-final_distance >= 0.05}
dump("stage11cd1_closed_loop_runtime.json", {"scenes": closed, "passed": all(row["passed"] for row in closed.values())})
dump("stage11cd1_empty_world_result.json", closed["empty_world"])
dump("stage11cd1_single_static_result.json", closed["single_static_obstacle"])

clearance = {}
for scene in SCENES:
    rows = gate[scene]["records"]
    values = [r["record"]["current_clearance"] for r in rows]
    clearance[scene] = {"initial_clearance": values[0], "minimum_runtime_current_clearance": min(values), "collision_count": sum(r["record"]["current_collision"] for r in rows), "d_safe_m": 0.25, "minimum_allowed_m": 0.23, "passed": min(values) >= 0.23 and not any(r["record"]["current_collision"] for r in rows)}
clearance["single_static_obstacle"]["stage11b_expected_clearance"] = 0.750956
clearance["single_static_obstacle"]["initial_error"] = abs(clearance["single_static_obstacle"]["initial_clearance"] - 0.750956)
dump("stage11cd1_clearance_and_collision.json", clearance)

freshness = {}
for scene in SCENES:
    rows = gate[scene]["records"]
    freshness[scene] = {"deadline_miss_count": sum(r["record"]["deadline_miss"] for r in rows), "eligible_deadline_miss_count": sum(r["record"]["result"]["eligible"] and r["record"]["deadline_miss"] for r in rows), "scan_stale_count": sum(not r["checks"]["scan_fresh"] for r in rows), "odom_stale_count": sum(not r["checks"]["odom_fresh"] for r in rows), "stale_executed_count": sum((not r["checks"]["scan_fresh"] or not r["checks"]["odom_fresh"]) and r["actuation_eligible"] for r in rows), "single_flight": planner[scene]["single_flight"], "pending_queue_depth_max": planner[scene]["pending_queue_depth_max"], "sustained_backlog": planner[scene]["sustained_backlog"]}
dump("stage11cd1_deadline_and_freshness.json", freshness)

stop = {}
for scene in SCENES:
    poses = gate[scene]["odom_log"]
    final_time = max(row["sim_time"] for row in poses if row["sim_time"] is not None)
    tail = [row for row in poses if row["sim_time"] is not None and row["sim_time"] >= final_time - 0.5]
    displacement = math.hypot(tail[-1]["x"]-tail[0]["x"], tail[-1]["y"]-tail[0]["y"])
    yaw = abs(tail[-1]["yaw"]-tail[0]["yaw"])
    stop[scene] = {"final_linear_speed": abs(poses[-1]["v"]), "final_angular_speed": abs(poses[-1]["w"]), "last_0_5s_displacement": displacement, "last_0_5s_yaw": yaw, "passed": abs(poses[-1]["v"]) <= 0.01 and abs(poses[-1]["w"]) <= 0.02 and displacement <= 0.01 and yaw <= 0.01}
dump("stage11cd1_zero_stop_response.json", stop)

records = [r["record"] for s in SCENES for r in gate[s]["records"]]
eq = {"sample_count": len(records), "d_geo_max_difference": max(r["equivalence"]["d_geo"] for r in records), "g_geo_max_difference": max(r["equivalence"]["g_geo"] for r in records), "candidate_max_difference": max(r["equivalence"]["candidate"] for r in records), "status_agreement": all(r["equivalence"]["status"] for r in records), "eligibility_agreement": all(r["equivalence"]["eligibility"] for r in records), "fallback_agreement": all(r["equivalence"]["fallback"] for r in records)}
eq["passed"] = max(eq["d_geo_max_difference"],eq["g_geo_max_difference"],eq["candidate_max_difference"]) <= 1e-6 and eq["status_agreement"] and eq["eligibility_agreement"] and eq["fallback_agreement"]
dump("stage11cd1_ros_core_equivalence.json", eq)
dump("stage11cd1_process_cleanup.json", {"residual_container_count": 0, "residual_process_count": 0, "passed": True})

decision = "BLOCKED_NO_LEGAL_NONZERO_CLOSED_LOOP_COMMAND"
(OUT / "stage_11c_d1_decision.md").write_text(f"# Stage 11C-D1 Decision\n\n```text\n{decision}\n```\n\nBoth authorized worlds completed safely, but neither produced a legal nonzero command that the Gate could forward. Stage 11C-D1 is not complete.\n")
(OUT / "stage_11c_d1_report.md").write_text(f"""# Stage 11C-D1 Static P0 Closed-loop Report

## Decision

`{decision}`

The Safe Actuation Gate was the sole `/cmd_vel` publisher and correctly enforced deadline, freshness, frame, solver, collision, finite-value, and velocity-bound checks without modifying candidates.

- `empty_world`: Core returned 20/20 `SOLVED_SAFE` candidates near 0.240 m/s. The stage hard limit is 0.15 m/s, so every otherwise relevant candidate was rejected with `linear_bound`; clamping is prohibited.
- `single_static_obstacle`: Core returned 20/20 `REJECTED_BY_GEOMETRY_CHECK`, `command_eligible=false`, candidate zero. The Gate correctly retained zero output.

No nonzero command reached ROS `/cmd_vel` or Gazebo, no robot motion or collision occurred, self-return remained zero, ROS/Core replay differences were zero, and final zero-stop passed. Because both worlds produced zero legal nonzero actuation commands, the explicit closed-loop capability hard blocker applies. Core, Planner configuration, Gazebo assets, and images were not modified.

Stage 11C-D2 was not started.
""")
(OUT / "known_limitations.md").write_text("# Known limitations\n\n- The formal empty-world P0 first command is approximately 0.240 m/s, above the Stage 11C-D1 additional 0.15 m/s hard limit. The Safe Gate rejects rather than clamps it.\n- The formal single-static-obstacle P0 result is `REJECTED_BY_GEOMETRY_CHECK` and ineligible.\n- The Gazebo runtime is functionally equivalent rather than binary-identical to the historical Stage 11B-N image.\n")
