"""Scene-split Stage 10 RGB semantic dataset."""

from __future__ import annotations
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import Dataset


class RGBSemanticDataset(Dataset):
    def __init__(self,path):
        data=np.load(Path(path),allow_pickle=False); self.images=data['images']; self.masks=data['semantic_masks']; self.scene_ids=data['scene_ids']; self.occluded=data['occluded_masks']
    def __len__(self): return len(self.images)
    def __getitem__(self,index):
        image=torch.from_numpy(self.images[index].transpose(2,0,1).copy()).float()/255.; mask=torch.from_numpy(self.masks[index].astype(np.int64)); return {'image':image,'target':mask,'scene_id':int(self.scene_ids[index]),'occluded_mask':torch.from_numpy(self.occluded[index])}
