# Stage 10 Visual Identifiability Audit

## Decision before implementation

`CONTINUE_WITH_INDEPENDENT_APPEARANCE_RENDERER`

Stage 07 `rgb_debug_image` is unsuitable for learning: each semantic prism is
filled directly with `SemanticObstacle.visual_color`, and the deterministic
examples use a fixed class-to-color table. Training on it would teach
`color = class`. It is prohibited as Stage 10 model input.

No licensed local real-image semantic dataset or attributable cached RGB model
weights were found. The only local `.pt` is the project-generated Stage 04 LiDAR
clearance model and is unrelated to RGB perception; it will not be used.

## Identifiability after removing fixed colors

The Stage 07 convex-prism RGB debug rendering has no sufficient class structure
after removing fixed colors: prism faces are otherwise uniform. Stage 10 will
therefore use an independent procedural appearance renderer while retaining the
Stage 07 Oracle semantic mask as label only. The renderer makes classes
identifiable through coarse structure:

- STATIC: wall/box/column silhouettes;
- HUMAN: head plus narrow torso/limb proportions;
- VEHICLE: low wide body with wheel/window structure;
- ROBOT: compact chassis, upper module, and antenna/sensor structure.

These are synthetic icons, not photo-realistic objects or evidence for real
camera deployment.

## Leakage controls

- All classes draw colors from the same palette; a color can occur in every
  class, and every class varies color.
- Class-independent texture, lighting, contrast, exposure, blur, noise,
  occlusion, background, and scale are randomized.
- Semantic and instance masks are outputs/labels and never model inputs.
- Scene ID, geometry seed, appearance seed, camera seed, and split are recorded.
- Splits use disjoint scene IDs and seeds; variants of one base scene do not cross
  splits.
- Filenames contain only numeric scene IDs and split, not class names.

The audit permits synthetic-domain training. It does not validate real RGB,
silent calibration-error detection, or dynamic-agent prediction.
