"""Reliability-weighted point and query margins over observable LiDAR points."""
import time,numpy as np

MARGINS=np.asarray([0.,0.,.35,.20,.15])
class SemanticMarginProvider:
    def __init__(self,points_xy,probabilities,projection_valid,observable_valid=None,image_available=True,image_age_s=0.,gate=True,length=.8,width=.5,truncation=8.):
        from sgcf_nrmp.semantic.explicit_failure_gate import explicit_failure_reliability
        started=time.perf_counter(); self.points=np.asarray(points_xy,float); self.observable=np.ones(len(self.points),bool) if observable_valid is None else np.asarray(observable_valid,bool); self.length,self.width,self.truncation=length,width,truncation; p=np.asarray(probabilities,float)
        projection_valid=np.asarray(projection_valid,bool); classes=np.argmax(p,axis=1) if len(p) else np.empty(0,dtype=int)
        reasons=[]
        if gate:
            if not image_available: reasons.append("RGB_DROPOUT")
            if image_age_s>.1: reasons.append("OUTDATED_IMAGE")
            if len(projection_valid) and not np.any(projection_valid): reasons.append("INVALID_PROJECTION")
            if len(classes) and np.all(classes==0): reasons.append("UNKNOWN")
        self.explicit_failure_reasons=tuple(reasons); self.explicit_failure_active=bool(reasons); self.gate_enabled=bool(gate)
        gate_started=time.perf_counter(); reliability=explicit_failure_reliability(p,projection_valid,image_available,image_age_s) if gate else np.ones(len(p)); gate_ms=(time.perf_counter()-gate_started)*1000.
        margin_started=time.perf_counter(); self.point_margin=reliability*(p@MARGINS); self.point_margin=np.where(self.observable,self.point_margin,0.); point_ms=(time.perf_counter()-margin_started)*1000.; self.gate_reliability=reliability
        self.preparation_timings_ms={"r1_gate_ms":gate_ms,"point_semantic_margin_ms":point_ms,"semantic_provider_total_ms":(time.perf_counter()-started)*1000.}
    def query_margins(self,queries):
        q=np.asarray(queries,float)
        if len(self.points)==0 or not np.any(self.observable): return np.zeros(len(q),dtype=float)
        delta=self.points[None]-q[:,None,:2]; c=np.cos(q[:,2])[:,None]; s=np.sin(q[:,2])[:,None]; local=np.stack((c*delta[...,0]+s*delta[...,1],-s*delta[...,0]+c*delta[...,1]),-1); d=np.linalg.norm(np.maximum(np.abs(local)-[self.length/2,self.width/2],0),axis=-1); d[:,~self.observable]=np.inf; geo=np.minimum(d.min(1),self.truncation); eff=np.min(d-self.point_margin[None],axis=1); margin=np.maximum(0,geo-eff)
        if np.any(margin< -1e-6) or np.any(margin>.350001): raise AssertionError("semantic margin bound violated")
        return margin
