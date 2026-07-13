# Deployable Reliability Feature Definition Audit

The proposed deployable feature vector contains projection validity, painted maximum probability, entropy, UNKNOWN probability, image-border distance, projected UV, LiDAR range and beam index, neighboring range difference, neighboring painted-class disagreement, local probability disagreement, distance to semantic boundary, valid-neighbor ratio, RGB availability, image age, and frame-level projection/entropy/disagreement/transition consistency statistics.

It explicitly excludes true translation/rotation error, GT class, correctness GT, reliability GT, winning offset, margin GT, Oracle instance/depth, world geometry, hidden obstacles, and future images.

These exclusions are correct for deployment, but they make a class of alignment errors unidentifiable: a correctly projected HUMAN point in a uniform HUMAN region and a misprojected STATIC point landing in the same region can have identical allowed features. Boundary-consistency features are soft evidence only and are zero in both uniform-region cases.
