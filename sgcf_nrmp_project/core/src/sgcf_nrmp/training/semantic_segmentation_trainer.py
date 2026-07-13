"""Minimal deterministic CPU semantic training helpers."""
import random,numpy as np,torch

def seed_all(seed): random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.use_deterministic_algorithms(True)
def train_epoch(model,loader,optimizer,criterion):
 model.train(); total=0.
 for batch in loader:
  optimizer.zero_grad(set_to_none=True); loss=criterion(model(batch['image']),batch['target']); loss.backward(); optimizer.step(); total+=float(loss)*len(batch['image'])
 return total/len(loader.dataset)
@torch.no_grad()
def evaluate_loss(model,loader,criterion):
 model.eval(); return sum(float(criterion(model(b['image']),b['target']))*len(b['image']) for b in loader)/len(loader.dataset)
