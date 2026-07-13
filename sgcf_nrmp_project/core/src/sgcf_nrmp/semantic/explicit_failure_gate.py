"""R1 gate for directly observable semantic failures only."""
import numpy as np

def explicit_failure_reliability(probabilities,projection_valid,image_available,image_age_s,max_image_age_s=.1):
    p=np.asarray(probabilities,float); valid=np.asarray(projection_valid,bool); classes=np.argmax(p,axis=1); enabled=bool(image_available and image_age_s<=max_image_age_s); return (valid&(classes!=0)&enabled).astype(float)
