"""Sharded geometry dataset schema, loader and validation."""

from .geometry_dataset import GeometryClearanceDataset
from .validation import validate_dataset

__all__ = ["GeometryClearanceDataset", "validate_dataset"]
