#!/usr/bin/env python3
"""Smoke overfit gate and bounded Tiny U-Net training."""
import json,time
from pathlib import Path
import numpy as np,torch,yaml
from torch.utils.data import DataLoader,Subset
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all,train_epoch,evaluate_loss

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; cfg=yaml.safe_load((ROOT/'core/configs/train/stage_10_semantic_training.yaml').read_text()); model_cfg=yaml.safe_load((ROOT/'core/configs/model/tiny_semantic_segmentation.yaml').read_text()); seed_all(cfg['seed']); torch.set_num_threads(4)
train=RGBSemanticDataset(OUT/'dataset/train.npz'); val=RGBSemanticDataset(OUT/'dataset/validation.npz'); counts=np.bincount(train.masks.ravel(),minlength=5); weights=np.sqrt(counts.sum()/np.maximum(counts,1)); weights=weights/weights.mean(); criterion=torch.nn.CrossEntropyLoss(weight=torch.tensor(weights,dtype=torch.float32))
def make(): return TinySemanticSegmentation(model_cfg['class_count'],model_cfg['base_channels'])
# Mandatory 48-image overfit gate.
over=Subset(train,range(min(cfg['overfit_image_count'],len(train)))); loader=DataLoader(over,batch_size=cfg['batch_size'],shuffle=True,generator=torch.Generator().manual_seed(cfg['seed'])); model=make(); opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay']); initial=None; last=None
for epoch in range(cfg['overfit_epochs']):
 last=train_epoch(model,loader,opt,criterion); initial=last if initial is None else initial
overfit_pass=bool(last<initial*.55)
Path(OUT/'overfit_gate.json').write_text(json.dumps({'images':len(over),'initial_loss':initial,'final_loss':last,'relative_loss':last/initial,'pass':overfit_pass},indent=2)+'\n')
if not overfit_pass: raise SystemExit('BLOCKED_MODEL_OR_DATA_PIPELINE: 48-image overfit gate failed')
# Reinitialize for bounded full training; checkpoint selected only by validation loss.
seed_all(cfg['seed']); model=make(); opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay']); train_loader=DataLoader(train,batch_size=cfg['batch_size'],shuffle=True,generator=torch.Generator().manual_seed(cfg['seed'])); val_loader=DataLoader(val,batch_size=cfg['batch_size']); history=[]; best=float('inf'); stale=0; started=time.perf_counter()
for epoch in range(cfg['max_epochs']):
 tl=train_epoch(model,train_loader,opt,criterion); vl=evaluate_loss(model,val_loader,criterion); history.append({'epoch':epoch+1,'train_loss':tl,'validation_loss':vl})
 if vl<best-1e-4: best=vl; stale=0; torch.save({'model':model.state_dict(),'model_config':model_cfg,'train_config':cfg,'class_counts':counts.tolist()},OUT/'best_rgb_semantic_model.pt')
 else: stale+=1
 if stale>=cfg['early_stopping_patience']: break
Path(OUT/'training_history.json').write_text(json.dumps({'history':history,'best_validation_loss':best,'elapsed_s':time.perf_counter()-started},indent=2)+'\n'); (OUT/'training_config.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False)); Path(OUT/'model_architecture.json').write_text(json.dumps({'name':'TinySemanticSegmentation','parameter_count':make().parameter_count,'class_count':5,'base_channels':model_cfg['base_channels'],'pretrained':False,'input':'current_rgb_only'},indent=2)+'\n')
print(json.dumps({'overfit_pass':overfit_pass,'epochs':len(history),'best_validation_loss':best,'parameters':model.parameter_count},indent=2))
