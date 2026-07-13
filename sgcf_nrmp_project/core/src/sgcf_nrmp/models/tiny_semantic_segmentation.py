"""Small U-Net-style semantic segmentation model trained from scratch."""

import torch
from torch import nn
import torch.nn.functional as F


def _block(a,b): return nn.Sequential(nn.Conv2d(a,b,3,padding=1),nn.ReLU(inplace=True),nn.Conv2d(b,b,3,padding=1),nn.ReLU(inplace=True))


class TinySemanticSegmentation(nn.Module):
    def __init__(self,class_count=5,base_channels=16):
        super().__init__(); b=base_channels; self.e1=_block(3,b); self.e2=_block(b,b*2); self.mid=_block(b*2,b*4); self.d2=_block(b*4+b*2,b*2); self.d1=_block(b*2+b,b); self.head=nn.Conv2d(b,class_count,1)
    def forward(self,x):
        a=self.e1(x); b=self.e2(F.max_pool2d(a,2)); m=self.mid(F.max_pool2d(b,2)); d2=self.d2(torch.cat((F.interpolate(m,size=b.shape[-2:],mode='bilinear',align_corners=False),b),1)); d1=self.d1(torch.cat((F.interpolate(d2,size=a.shape[-2:],mode='bilinear',align_corners=False),a),1)); return self.head(d1)
    @property
    def parameter_count(self): return sum(p.numel() for p in self.parameters())
