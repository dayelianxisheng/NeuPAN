"""Current-RGB-only predictor wrapper."""
import numpy as np
import torch
from sgcf_nrmp.perception.semantic_confidence import confidence_classes


class RGBSemanticPredictor:
    def __init__(self,model,device='cpu'): self.model=model.to(device).eval(); self.device=torch.device(device)
    def preprocess(self,image_rgb):
        x=np.asarray(image_rgb,np.uint8); return torch.from_numpy(x.transpose(2,0,1).copy()).float().div(255.).unsqueeze(0).to(self.device)
    def predict_logits(self,image_tensor): return self.model(image_tensor.to(self.device))
    def predict_probabilities(self,image_tensor): return torch.softmax(self.predict_logits(image_tensor),dim=1)
    def predict_semantic_map(self,image_tensor,probability_threshold=None,entropy_threshold=None): return confidence_classes(self.predict_probabilities(image_tensor),probability_threshold,entropy_threshold)[0]
