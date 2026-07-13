# Coordinate and Frame Contract

All transforms use `T_target_source`, SI metres/seconds, radians, right-handed
coordinates, and counter-clockwise positive yaw about +z.

| Frame | Axes and purpose |
|---|---|
| `world` | Static simulation inertial frame: x/y horizontal, z up |
| `odom` | Locally continuous navigation frame; identity to world in static preparation |
| `base_footprint` | Ground projection of robot rectangle centre; x forward, y left, z up |
| `base_link` | Rigid body centre, 0.1 m above `base_footprint`; x forward, y left, z up |
| `lidar_link` | 0.1 m above `base_link`; zero scan angle +x, increasing angle toward +y |
| `camera_link` | Standard robot camera body axes: x forward, y left, z up |
| `camera_optical_frame` | x right, y down, z forward, matching Stage 07 |

`base_footprint` owns the Planner `[x,y,yaw]` reference. `base_link` owns the
physical collision box. Their x/y/yaw coincide; only z differs.

The camera is 0.8 m above the LiDAR. The frozen Stage 07 transform is:

```text
T_camera_optical_frame_lidar_link =
[[0, -1,  0, 0.0],
 [0,  0, -1, 0.8],
 [1,  0,  0, 0.0],
 [0,  0,  0, 1.0]]
```

No implicit axis swap is permitted inside adapters.
