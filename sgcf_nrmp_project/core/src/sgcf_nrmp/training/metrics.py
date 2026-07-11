"""Streaming weighted averages used by the trainer."""

from dataclasses import dataclass


@dataclass
class AverageMeter:
    total: float = 0.0
    count: int = 0

    def update(self, value: float, count: int) -> None:
        self.total += value * count; self.count += count

    @property
    def average(self) -> float:
        return self.total / max(self.count, 1)
