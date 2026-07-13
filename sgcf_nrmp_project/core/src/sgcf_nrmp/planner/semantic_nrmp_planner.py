"""Semantic checker adapter; planner optimization remains GTNRMPPlanner."""
import time
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker

class SemanticObservableChecker:
    def __init__(self,exact_checker:ExactObservableChecker,margin_provider): self.exact_checker,self.margin_provider=exact_checker,margin_provider; self.last_semantic_latency_ms=0.; self.preparation_timings_ms=dict(getattr(margin_provider,"preparation_timings_ms",{}))
    def linearization(self,states): return self.exact_checker.linearization(states)
    def recheck_observable_trajectory(self,states,d_safe): return self.exact_checker.recheck_observable_trajectory(states,d_safe)
    def distance(self,states): return self.exact_checker.distance(states)
    def semantic_margins(self,states):
        t=time.perf_counter(); value=self.margin_provider.query_margins(states); self.last_semantic_latency_ms=(time.perf_counter()-t)*1000; return value
