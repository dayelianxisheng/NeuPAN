# Known Limitations

- The mixed STATIC/HUMAN/VEHICLE diagnostic scene remains safely rejected in P0 and does not establish navigation completeness.
- Stage 10 and semantic prediction were not used.
- This is a Gazebo differential-drive baseline, not Mowen hardware validation.
- The reference-path correction is Stage 15B protocol data, not a general global planner.
- No formal safety guarantee is claimed.
