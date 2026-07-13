"""Interpretable UNKNOWN conversion for semantic probability maps."""
import torch


def semantic_entropy(probabilities,eps=1e-8): return -(probabilities.clamp_min(eps)*probabilities.clamp_min(eps).log()).sum(dim=1)
def confidence_classes(probabilities,probability_threshold=None,entropy_threshold=None):
    confidence,classes=probabilities.max(dim=1); unknown=torch.zeros_like(classes,dtype=torch.bool)
    if probability_threshold is not None: unknown|=confidence<float(probability_threshold)
    if entropy_threshold is not None: unknown|=semantic_entropy(probabilities)>float(entropy_threshold)
    return classes.masked_fill(unknown,0),unknown
