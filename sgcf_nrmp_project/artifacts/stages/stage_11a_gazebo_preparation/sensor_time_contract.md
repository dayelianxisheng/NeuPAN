# Sensor Time and Synchronization Contract

All runtime messages must use Gazebo simulation time. A Planner cycle captures
one transform snapshot and never mixes transforms from different timestamps.

- LiDAR stamp: acquisition completion time for the scan.
- RGB stamp: exposure/simulation frame time.
- State stamp: odometry sample time.
- Planner stamp: newest accepted LiDAR stamp.
- RGB/LiDAR absolute skew must not exceed 50 ms.
- RGB age must not exceed 100 ms, preserving Stage 08.
- LiDAR age must not exceed 200 ms (one Planner period).
- Transform age must not exceed 50 ms.
- Missing image, stale image, invalid transform/projection, or UNKNOWN invokes
  R1 and sets semantic contribution to zero.

No ROS message filter is implemented in Stage 11A.
