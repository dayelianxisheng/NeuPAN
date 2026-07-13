# Semantic Margin Integration

The persistent QP now accepts an optional nonnegative horizon vector. Existing callers omit it and receive zeros. Semantic mode evaluates the fixed query margin at the nominal trajectory once per SCP iteration and applies it only to the constraint right-hand side:

`d_geo + g_geo^T(q-q_nom) + slack >= d_safe + m_sem`.

The exact observable checker still supplies distance, gradient, and final trajectory recheck. Executed-pose observable clearance is also evaluated by the exact checker, never by the semantic adapter. Margins are shape-checked and clipped only at the mathematical class maximum after rejecting out-of-range inputs.

