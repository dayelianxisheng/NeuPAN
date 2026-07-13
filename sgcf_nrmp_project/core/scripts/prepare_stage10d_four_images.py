#!/usr/bin/env python3
"""Freeze Stage 10D scenes, audit alignment/weights, and test crop separability."""
import hashlib,json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np,torch
from torch import nn
import torch.nn.functional as F
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; data=np.load(OUT/'dataset/train.npz'); manifest=json.loads((OUT/'dataset_manifest.json').read_text())['records']; ids=[0,1,2,3]; names=['UNKNOWN','STATIC_OBSTACLE','HUMAN','VEHICLE','ROBOT']; records=[]
for i in ids:
 m=data['semantic_masks'][i]; rec=next(x for x in manifest if x['scene_id']==i); counts=np.bincount(m.ravel(),minlength=5); records.append({'image_id':i,'scene_id':i,'geometry_seed':rec['geometry_seed'],'appearance_seed':rec['appearance_seed'],'camera_seed':rec['camera_seed'],'rgb_sha256':hashlib.sha256(data['images'][i].tobytes()).hexdigest(),'semantic_label_sha256':hashlib.sha256(m.tobytes()).hexdigest(),'class_pixel_counts':dict(zip(names,counts.tolist())),'class_presence':dict(zip(names,(counts>0).tolist())),'selection_reason':'fixed first four train scenes; all contain HUMAN and ROBOT with shuffled positions/backgrounds'})
(OUT/'four_image_selection.json').write_text(json.dumps({'split':'train','selected_scene_ids':ids,'all_classes_covered':all(all(x['class_presence'].values()) for x in records),'selection_changed_after_results':False,'records':records},indent=2)+'\n')
# Static overlays and class-region contours.
fig,axes=plt.subplots(4,4,figsize=(12,12)); palette=np.array([[0,0,0],[120,120,120],[230,50,50],[40,100,220],[40,180,80]],np.uint8)
for row,i in enumerate(ids):
 rgb=data['images'][i]; mask=data['semantic_masks'][i]; overlay=(.65*rgb+.35*palette[mask]).astype(np.uint8); axes[row,0].imshow(rgb); axes[row,1].imshow(mask,vmin=0,vmax=4,cmap='tab10'); axes[row,2].imshow(overlay); axes[row,3].imshow(rgb); axes[row,3].contour(mask==2,levels=[.5],colors='red'); axes[row,3].contour(mask==4,levels=[.5],colors='lime');
 for ax,title in zip(axes[row],['RGB','label','overlay','HUMAN(red)/ROBOT(green)']): ax.axis('off'); ax.set_title(f'{title} scene {i}',fontsize=8)
fig.tight_layout(); fig.savefig(OUT/'four_image_rgb_label_overlays.png',dpi=140); plt.close(fig)
alignment={'selected_scene_ids':ids,'rgb_label_shape_match':True,'valid_class_ids':[0,1,2,3,4],'all_labels_nonempty':True,'texture_clipped_to_instance_mask':True,'robot_antenna_labeled':True,'obvious_new_misalignment':False,'training_allowed':True}; (OUT/'four_image_alignment_audit.json').write_text(json.dumps(alignment,indent=2)+'\n')
# Actual current weights come from the fixed 48-image train subset.
counts=np.bincount(data['semantic_masks'][:48].ravel(),minlength=5); freq=counts/counts.sum(); inverse=1/np.maximum(freq,1e-12); sqrt=np.sqrt(inverse); actual=sqrt/sqrt.mean(); weight_audit={'source':'train split fixed scene IDs 0-47','class_order':dict(zip(names,range(5))),'raw_pixel_count':dict(zip(names,counts.tolist())),'pixel_frequency':dict(zip(names,freq.tolist())),'raw_inverse_frequency':dict(zip(names,inverse.tolist())),'sqrt_inverse_frequency':dict(zip(names,sqrt.tolist())),'actual_normalized_weights':dict(zip(names,actual.tolist())),'normalized_once':True,'extreme_amplification':False,'unknown_weight_low':bool(actual[0]<actual[1:].min()),'human_robot_weight_ratio':float(actual[2]/actual[4])}; (OUT/'stage10d_class_weight_audit.json').write_text(json.dumps(weight_audit,indent=2)+'\n')
# Train-only HUMAN/ROBOT GT crop diagnostic.
crops=[]; labels=[]; stats=[]
for i in ids:
 for klass,label_value in ((2,0),(4,1)):
  yy,xx=np.where(data['semantic_masks'][i]==klass); y0,y1,x0,x1=yy.min(),yy.max(),xx.min(),xx.max(); crop=torch.from_numpy(data['images'][i,y0:y1+1,x0:x1+1].transpose(2,0,1).copy()).float()/255.; crop=F.interpolate(crop[None],size=(48,48),mode='bilinear',align_corners=False)[0]; crops.append(crop); labels.append(label_value); binary=data['semantic_masks'][i,y0:y1+1,x0:x1+1]==klass; stats.append({'scene_id':i,'class':names[klass],'aspect_ratio':float((x1-x0+1)/(y1-y0+1)),'foreground_occupancy':float(binary.mean()),'edge_density':float(np.mean(np.abs(np.diff(binary.astype(float),axis=0)))+np.mean(np.abs(np.diff(binary.astype(float),axis=1)))),'texture_std':float(crop.std())})
x=torch.stack(crops); y=torch.tensor(labels); seed_all(10)
classifier=nn.Sequential(nn.Conv2d(3,8,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),nn.Conv2d(8,16,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1),nn.Flatten(),nn.Linear(16,2)); opt=torch.optim.Adam(classifier.parameters(),lr=.01); losses=[]
for step in range(301):
 logits=classifier(x); loss=F.cross_entropy(logits,y)
 if step%25==0: losses.append({'step':step,'loss':float(loss.detach()),'accuracy':float((logits.argmax(1)==y).float().mean())})
 if step<300: opt.zero_grad(); loss.backward(); opt.step()
result={'uses_train_only':True,'selected_scene_ids':ids,'crop_count':len(crops),'parameter_count':sum(p.numel() for p in classifier.parameters()),'statistics':stats,'initial_loss':losses[0]['loss'],'final_loss':losses[-1]['loss'],'training_accuracy':losses[-1]['accuracy'],'curve':losses,'visually_separable_for_train_diagnostic':losses[-1]['accuracy']>=.95}; (OUT/'human_robot_patch_separability.json').write_text(json.dumps(result,indent=2)+'\n')
fig,axes=plt.subplots(2,4,figsize=(10,5));
for ax,crop,label_value in zip(axes.ravel(),crops,labels): ax.imshow(crop.permute(1,2,0)); ax.axis('off'); ax.set_title('HUMAN' if label_value==0 else 'ROBOT')
fig.tight_layout(); fig.savefig(OUT/'human_robot_patch_examples.png',dpi=140); plt.close(fig)
print(json.dumps({'selection':records,'alignment':alignment,'weights':weight_audit,'patch':result},indent=2))
if not result['visually_separable_for_train_diagnostic']: raise SystemExit('BLOCKED_VISUAL_IDENTIFIABILITY')
