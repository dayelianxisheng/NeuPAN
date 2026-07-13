#!/usr/bin/env python3
"""Prediction-collapse timeline and mandatory single-image overfit diagnosis."""
import json,math
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np,torch
from torch.utils.data import DataLoader,Subset
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; seed_all(10); torch.set_num_threads(4); dataset=RGBSemanticDataset(OUT/'dataset/train.npz'); selected=Subset(dataset,range(48)); counts=np.bincount(dataset.masks[:48].ravel(),minlength=5); sqrt_weights=np.sqrt(counts.sum()/np.maximum(counts,1)); sqrt_weights/=sqrt_weights.mean(); criterion=torch.nn.CrossEntropyLoss(weight=torch.tensor(sqrt_weights,dtype=torch.float32)); names=['UNKNOWN','STATIC_OBSTACLE','HUMAN','VEHICLE','ROBOT']
def evaluate(model,subset):
 confusion=np.zeros((5,5),np.int64); prob_sum=np.zeros(5); prob_max=np.zeros(5); pixels=0
 model.eval()
 with torch.no_grad():
  for b in DataLoader(subset,batch_size=8):
   logits=model(b['image']); prob=logits.softmax(1); pred=prob.argmax(1); target=b['target']; confusion+=np.bincount((target*5+pred).numpy().ravel(),minlength=25).reshape(5,5); prob_sum+=prob.sum((0,2,3)).numpy(); prob_max=np.maximum(prob_max,prob.amax((0,2,3)).numpy()); pixels+=target.numel()
 pred_count=confusion.sum(0); recall=np.diag(confusion)/np.maximum(confusion.sum(1),1); precision=np.diag(confusion)/np.maximum(pred_count,1); f1=2*precision*recall/np.maximum(precision+recall,1e-12)
 return {'predicted_pixel_count':dict(zip(names,pred_count.tolist())),'predicted_pixel_fraction':dict(zip(names,(pred_count/pixels).tolist())),'mean_probability':dict(zip(names,(prob_sum/pixels).tolist())),'maximum_probability':dict(zip(names,prob_max.tolist())),'confusion_matrix':confusion.tolist(),'pixel_accuracy':float(np.trace(confusion)/confusion.sum()),'macro_f1':float(np.mean(f1)),'per_class_recall':dict(zip(names,recall.tolist()))}
# Reproduce current 48-image collapse at epochs 0/12/24 for diagnosis only.
model=TinySemanticSegmentation(); opt=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=0.); loader=DataLoader(selected,batch_size=8,shuffle=True,generator=torch.Generator().manual_seed(10)); timeline={'epoch_0':evaluate(model,selected)}
for epoch in range(1,25):
 model.train()
 for b in loader: opt.zero_grad(set_to_none=True); loss=criterion(model(b['image']),b['target']); loss.backward(); opt.step()
 if epoch in (12,24): timeline[f'epoch_{epoch}']=evaluate(model,selected)
(OUT/'prediction_class_collapse.json').write_text(json.dumps({'interpretation':'Model collapses predominantly to UNKNOWN/STATIC during the current 48-image gate.','timeline':timeline},indent=2)+'\n')
fig,ax=plt.subplots(figsize=(8,4)); x=np.arange(5); width=.25
for j,(key,value) in enumerate(timeline.items()): ax.bar(x+(j-1)*width,list(value['predicted_pixel_fraction'].values()),width,label=key)
ax.set_xticks(x,names,rotation=20); ax.set_ylabel('predicted fraction'); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'prediction_class_collapse.png',dpi=150); plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(12,4));
for ax,(key,value) in zip(axes,timeline.items()): ax.imshow(value['confusion_matrix'],cmap='Blues'); ax.set_title(key); ax.set_xlabel('predicted'); ax.set_ylabel('target')
fig.tight_layout(); fig.savefig(OUT/'confusion_matrix_overfit_recheck.png',dpi=150); plt.close(fig)
# Single image contains all foreground classes by renderer construction.
single=Subset(dataset,[0]); seed_all(10); model=TinySemanticSegmentation(); opt=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=0.); loader=DataLoader(single,batch_size=1,shuffle=False); initial_state={n:p.detach().clone() for n,p in model.named_parameters()}; losses=[]; snapshots={}; gradient_record={}
for epoch in range(81):
 if epoch in (0,20,80): snapshots[str(epoch)]=evaluate(model,single)
 if epoch==80: break
 model.train(); b=next(iter(loader)); opt.zero_grad(set_to_none=True); logits=model(b['image']); loss=criterion(logits,b['target']); loss.backward()
 if epoch==0:
  groups={'encoder':['e1','e2'],'bottleneck':['mid'],'decoder':['d2','d1'],'classifier':['head']}
  all_grads=[]
  for group,prefixes in groups.items():
   vals=[p.grad.detach().norm().item() for n,p in model.named_parameters() if any(n.startswith(x) for x in prefixes) and p.grad is not None]; gradient_record[group+'_gradient_norm']=float(math.sqrt(sum(x*x for x in vals)))
  for p in model.parameters():
   if p.grad is not None: all_grads.append(p.grad.detach().reshape(-1))
  flat=torch.cat(all_grads); gradient_record['fraction_zero_gradients']=float((flat==0).float().mean()); gradient_record['fraction_nonfinite_gradients']=float((~torch.isfinite(flat)).float().mean()); gradient_record['optimizer_contains_all_trainable_parameters']=sum(p.numel() for g in opt.param_groups for p in g['params'])==sum(p.numel() for p in model.parameters() if p.requires_grad)
 opt.step(); losses.append(float(loss.detach()))
updates={}
for group,prefixes in {'encoder':['e1','e2'],'bottleneck':['mid'],'decoder':['d2','d1'],'classifier':['head']}.items(): updates[group+'_parameter_update_norm']=float(math.sqrt(sum(float((p.detach()-initial_state[n]).norm())**2 for n,p in model.named_parameters() if any(n.startswith(x) for x in prefixes))))
final=evaluate(model,single); result={'selected_scene_id':0,'contains_classes':np.unique(dataset.masks[0]).tolist(),'epochs':80,'initial_loss':losses[0],'final_loss':losses[-1],'relative_loss':losses[-1]/losses[0],'pixel_accuracy':final['pixel_accuracy'],'macro_f1':final['macro_f1'],'per_class_recall':final['per_class_recall'],'prediction_histogram':final['predicted_pixel_count'],'gradient_norms_first_batch':gradient_record,'parameter_update_norms':updates,'pass':bool(losses[-1]/losses[0]<.2 and min(final['per_class_recall'].values())>.8),'snapshots':snapshots}
(OUT/'single_image_overfit_stage10b.json').write_text(json.dumps(result,indent=2)+'\n'); (OUT/'gradient_flow_audit_stage10b.json').write_text(json.dumps({'single_image':gradient_record},indent=2)+'\n'); (OUT/'parameter_update_audit_stage10b.json').write_text(json.dumps({'single_image':updates},indent=2)+'\n')
fig,axes=plt.subplots(1,4,figsize=(14,3)); axes[0].imshow(dataset.images[0]); axes[0].set_title('RGB'); axes[1].imshow(dataset.masks[0],vmin=0,vmax=4,cmap='tab10'); axes[1].set_title('target')
for ax,(epoch,value) in zip(axes[2:],list(snapshots.items())[-2:]): ax.bar(names,list(value['predicted_pixel_fraction'].values())); ax.tick_params(axis='x',rotation=30); ax.set_title('prediction '+epoch)
for ax in axes[:2]: ax.axis('off')
fig.tight_layout(); fig.savefig(OUT/'single_image_prediction_progress_stage10b.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.plot(np.arange(1,len(losses)+1),losses,label='CE'); ax.set(xlabel='epoch',ylabel='loss',title='Single-image CE'); ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(OUT/'loss_component_curves_stage10b.png',dpi=150); plt.close(fig)
print(json.dumps({'collapse_final':timeline['epoch_24'],'single':result},indent=2))
if not result['pass']: raise SystemExit('BLOCKED_MODEL_OR_DATA_PIPELINE: single image cannot be memorized')
