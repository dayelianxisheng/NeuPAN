#!/usr/bin/env python3
"""Bounded single-image CE weighting and convergence diagnosis."""
import json,math
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np,torch
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; dataset=RGBSemanticDataset(OUT/'dataset/train.npz'); image=dataset[0]['image'][None]; target=dataset[0]['target'][None]; names=['UNKNOWN','STATIC_OBSTACLE','HUMAN','VEHICLE','ROBOT']; counts=np.bincount(dataset.masks[:48].ravel(),minlength=5); weights=np.sqrt(counts.sum()/np.maximum(counts,1)); weights/=weights.mean(); torch.set_num_threads(4)
def metrics(logits):
 pred=logits.argmax(1); cm=np.bincount((target*5+pred).numpy().ravel(),minlength=25).reshape(5,5); rec=np.diag(cm)/np.maximum(cm.sum(1),1); pre=np.diag(cm)/np.maximum(cm.sum(0),1); f1=2*pre*rec/np.maximum(pre+rec,1e-12); return {'pixel_accuracy':float(np.trace(cm)/cm.sum()),'macro_f1':float(np.mean(f1)),'per_class_recall':dict(zip(names,rec.tolist())),'prediction_fraction':dict(zip(names,(cm.sum(0)/cm.sum()).tolist()))}
def run(weighted):
 seed_all(10); model=TinySemanticSegmentation(); criterion=torch.nn.CrossEntropyLoss(weight=torch.tensor(weights,dtype=torch.float32) if weighted else None); opt=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=0.); records=[]; snapshots={}; previous={n:p.detach().clone() for n,p in model.named_parameters()}; last_grad=0.
 for step in range(601):
  model.eval()
  with torch.no_grad(): logits=model(image); loss=float(criterion(logits,target)); met=metrics(logits)
  if step%50==0:
   update=math.sqrt(sum(float((p.detach()-previous[n]).norm())**2 for n,p in model.named_parameters())); records.append({'step':step,'loss':loss,'gradient_norm_last_step':last_grad,'parameter_update_since_last_record':update,**met}); previous={n:p.detach().clone() for n,p in model.named_parameters()}; snapshots[str(step)]=logits.argmax(1)[0].numpy()
  if step==600: break
  model.train(); opt.zero_grad(set_to_none=True); value=criterion(model(image),target); value.backward(); grad=math.sqrt(sum(float(p.grad.detach().norm())**2 for p in model.parameters() if p.grad is not None)); opt.step()
  last_grad=grad
 losses=np.array([r['loss'] for r in records]); recent=records[-3:]; slope=float(np.polyfit([r['step'] for r in recent],[r['loss'] for r in recent],1)[0]); return model,records,snapshots,{'initial_loss':records[0]['loss'],'final_loss':records[-1]['loss'],'relative_loss':records[-1]['loss']/records[0]['loss'],'final_metrics':records[-1],'recent_20_percent_loss_slope_per_step':slope,'still_decreasing':slope< -1e-5}
unweighted_model,u_records,u_snaps,u_summary=run(False); weighted_model,w_records,w_snaps,w_summary=run(True)
comparison={'frozen_scene_id':0,'steps':600,'D0_unweighted_CE':u_summary,'D1_sqrt_inverse_frequency_CE':w_summary,'weight_source':'fixed train scenes 0-47','raw_pixel_counts':dict(zip(names,counts.tolist())),'actual_D1_weights':dict(zip(names,weights.tolist()))}; (OUT/'single_image_class_weight_comparison.json').write_text(json.dumps(comparison,indent=2)+'\n'); (OUT/'single_image_loss_comparison.json').write_text(json.dumps({'current_loss_is_ce_only':True,'dice_enabled':False,'D0_unweighted_CE':u_summary,'D1_weighted_CE':w_summary,'additional_loss_not_introduced':True},indent=2)+'\n'); (OUT/'single_image_convergence.json').write_text(json.dumps({'method':'D1_sqrt_inverse_frequency_CE','maximum_steps':600,'records':w_records,'summary':w_summary},indent=2)+'\n')
fig,ax=plt.subplots(); ax.plot([r['step'] for r in u_records],[r['loss'] for r in u_records],label='D0 unweighted CE'); ax.plot([r['step'] for r in w_records],[r['loss'] for r in w_records],label='D1 sqrt-weighted CE'); ax.set(xlabel='optimizer step',ylabel='CE loss'); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'single_image_convergence_curve.png',dpi=150); plt.close(fig)
fig,axes=plt.subplots(1,4,figsize=(13,3)); axes[0].imshow(dataset.images[0]); axes[0].set_title('RGB'); axes[1].imshow(dataset.masks[0],vmin=0,vmax=4,cmap='tab10'); axes[1].set_title('GT'); axes[2].imshow(w_snaps['100'],vmin=0,vmax=4,cmap='tab10'); axes[2].set_title('D1 step 100'); axes[3].imshow(w_snaps['600'],vmin=0,vmax=4,cmap='tab10'); axes[3].set_title('D1 step 600');
for ax in axes: ax.axis('off')
fig.tight_layout(); fig.savefig(OUT/'single_image_prediction_progress_stage10c.png',dpi=150); plt.close(fig)
print(json.dumps(comparison,indent=2))
