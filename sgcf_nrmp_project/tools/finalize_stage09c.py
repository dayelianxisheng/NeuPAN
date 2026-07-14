#!/usr/bin/env python3
"""Summarize Stage 09C offline and runtime evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess


ROOT = Path.cwd()
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_09c_collision_recovery"
RUNTIME = OUT / "runtime/single_static_obstacle"
LOGS = OUT / "logs/single_static_obstacle"


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=True) + "\n")


def main():
    planner = json.loads((RUNTIME / "planner_result.json").read_text())
    gate = json.loads((RUNTIME / "safe_gate_result.json").read_text())
    commands = []
    for line in (LOGS / "cmd_vel_gz.txt").read_text().splitlines():
        item = json.loads(line)
        commands.append((float(item.get("linear", {}).get("x", 0.0)), float(item.get("angular", {}).get("z", 0.0))))
    nonzero_gz = [item for item in commands if abs(item[0]) > 1e-12 or abs(item[1]) > 1e-12]
    forwarded = [
        tuple(row["final_command"])
        for row in gate["records"] if row["actuation_eligible"]
    ]
    gz_match_error = max(
        min(max(abs(g[0] - f[0]), abs(g[1] - f[1])) for f in forwarded)
        for g in nonzero_gz
    )
    candidate_error = max(
        max(abs(row["record"]["result"]["candidate"][i] - row["final_command"][i]) for i in (0, 1))
        for row in gate["records"] if row["actuation_eligible"]
    )
    transitions = []
    previous = None
    for row in gate["command_log"]:
        if row["phase"] != previous:
            transitions.append((row["phase"], row["sim_time"]))
            previous = row["phase"]
    phase_times = dict(transitions)
    odom = gate["odom_log"]
    start = [row for row in odom if row["sim_time"] <= phase_times["ACTIVE"]][-1]
    active_end = [row for row in odom if row["sim_time"] <= phase_times["FINAL_STOP"]][-1]
    final = odom[-1]
    final_half = [row for row in odom if row["sim_time"] >= final["sim_time"] - 0.5]
    goal = (4.0, 0.0)
    goal_distance = lambda row: math.hypot(goal[0] - row["x"], goal[1] - row["y"])
    progress = goal_distance(start) - goal_distance(active_end)
    records = planner["records"]
    minimum_d_geo = min(min(row["result"]["d_geo"]) for row in records if row["result"].get("d_geo"))
    equivalence = {
        key: max(row["equivalence"][key] for row in records)
        for key in ("candidate", "d_geo", "g_geo", "margin")
    }
    runtime = {
        "passed": True,
        "world": "single_static_obstacle",
        "mode": "P0",
        "active_duration_sim_s": phase_times["FINAL_STOP"] - phase_times["ACTIVE"],
        "goal_distance_reduction_m": progress,
        "nonzero_candidate_count": sum(any(abs(v) > 1e-12 for v in row["result"]["candidate"]) for row in records),
        "nonzero_ros_forward_count": gate["forwarded_nonzero_count"],
        "nonzero_gazebo_command_count": len(nonzero_gz),
        "minimum_d_geo_m": minimum_d_geo,
        "collision": False,
        "self_return_count": gate["self_return_count"],
        "deadline_miss_count": planner["deadline_miss_count"],
        "stale_count": planner["latency"]["stale_count"],
        "backlog_count": planner["latency"]["backlog_count"],
        "queue_depth_max": planner["pending_queue_depth_max"],
        "cpu_p95_ms": planner["latency"]["p95"],
        "final_linear_speed_mps": abs(final["v"]),
        "final_angular_speed_radps": abs(final["w"]),
        "last_half_second_translation_m": math.hypot(final_half[-1]["x"] - final_half[0]["x"], final_half[-1]["y"] - final_half[0]["y"]),
        "last_half_second_yaw_rad": abs(final_half[-1]["yaw"] - final_half[0]["yaw"]),
        "ros_core_equivalence": equivalence,
    }
    assert progress >= 0.05 and minimum_d_geo >= 0.23
    assert gate["self_return_count"] == 0 and planner["deadline_miss_count"] == 0
    assert planner["latency"]["stale_count"] == planner["latency"]["backlog_count"] == 0
    assert runtime["last_half_second_translation_m"] <= 0.01 and runtime["last_half_second_yaw_rad"] <= 0.01
    consistency = {
        "candidate_to_ros_max_component_error": candidate_error,
        "ros_to_gazebo_max_component_error": gz_match_error,
        "threshold": 1e-9,
        "passed": candidate_error <= 1e-9 and gz_match_error <= 1e-9,
    }
    assert consistency["passed"]
    dump("stage09c_single_static_closed_loop.json", runtime)
    dump("stage09c_command_consistency.json", consistency)

    residual_containers = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "name=sgcf_stage11cc"],
        text=True, capture_output=True, check=True,
    ).stdout.split()
    process_scan = []
    for proc in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            command = proc.read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(token in command for token in ("gz sim", "ros_gz_bridge", "stage11cc_planner_shadow_node", "stage11cd1_safe_actuation_gate")):
            if "finalize_stage09c.py" not in command:
                process_scan.append(command)
    cleanup = {
        "residual_stage_container_count": len(residual_containers),
        "residual_stage_process_count": len(process_scan),
        "passed": not residual_containers and not process_scan,
    }
    dump("stage09c_process_cleanup.json", cleanup)
    assert cleanup["passed"]


if __name__ == "__main__":
    main()
