"""Typed model output."""

from typing import NamedTuple
import torch


class ClearanceFieldOutput(NamedTuple):
    observable_clearance: torch.Tensor
    observable_collision_logit: torch.Tensor | None
