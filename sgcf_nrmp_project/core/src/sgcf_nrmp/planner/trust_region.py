"""Trust-region configuration and shrink policy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrustRegion:
    xy_m: float
    yaw_rad: float
    linear_velocity_mps: float
    angular_velocity_radps: float

    def scaled(self, factor: float) -> "TrustRegion":
        return TrustRegion(self.xy_m*factor,self.yaw_rad*factor,self.linear_velocity_mps*factor,self.angular_velocity_radps*factor)

    @classmethod
    def from_dict(cls,value: dict) -> "TrustRegion": return cls(**value)
