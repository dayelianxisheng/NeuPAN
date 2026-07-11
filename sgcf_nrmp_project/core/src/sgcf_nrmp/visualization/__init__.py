"""Stage-02 static visualizations."""

from .clearance_plot import compute_clearance_grid, plot_clearance_comparison, plot_gradient_field
from .scene_plot import plot_geometry, plot_lidar_rays

__all__ = [
    "compute_clearance_grid",
    "plot_clearance_comparison",
    "plot_geometry",
    "plot_gradient_field",
    "plot_lidar_rays",
]
