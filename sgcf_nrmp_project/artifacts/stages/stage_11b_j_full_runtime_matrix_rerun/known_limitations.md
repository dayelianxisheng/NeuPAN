# Known limitations

- Stage 11B-J stopped because `static_corridor` and `narrow_passage` runtime clearances differ from their authoritative manifest values by much more than 0.02 m.
- Both worlds place `<scale>` under `<include>`; SDFormat 1.9 reports that element as undefined, so the intended wall dimensions are not applied at runtime.
- Startup-latency repeats and complete R1 acceptance were not executed after the immediate-stop condition.
- `rgb_dropout_contract` did not complete its full sensor capture before the stop sequence.
- Some raw cleanup files falsely counted concurrent monitoring shells whose command text contained `gz sim`; executable-aware post-checks found no Gazebo residuals.
- `robot_obstacle` needed a SIGKILL after complete data capture when the server ignored INT and TERM. Data are retained, but clean shutdown is a known runtime limitation.
