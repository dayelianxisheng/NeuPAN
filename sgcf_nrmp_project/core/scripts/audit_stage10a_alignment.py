#!/usr/bin/env python3
"""Static sample/label audit executed before the Stage 10A minimal fix."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; data=np.load(OUT/'dataset/train.npz'); ids=list(range(12)); cmap=ListedColormap(['black','#777777','#e53935','#1e88e5','#43a047'])
fig,axes=plt.subplots(len(ids),5,figsize=(15,30))
illegal=[]; black=[]
for row,index in enumerate(ids):
 rgb=data['images'][index]; sem=data['semantic_masks'][index]; ins=data['instance_masks'][index]
 illegal.extend(np.unique(sem[(sem<0)|(sem>4)]).tolist()); black.append(bool(np.all(sem==0)))
 boundary=np.zeros_like(ins,dtype=bool); boundary[1:]|=ins[1:]!=ins[:-1]; boundary[:,1:]|=ins[:,1:]!=ins[:,:-1]
 color=(cmap(sem/4.)[:,:,:3]*255).astype(np.uint8); overlay=(.65*rgb+.35*color).astype(np.uint8); instance_overlay=rgb.copy(); instance_overlay[boundary]=[255,255,255]
 for ax,image,title in zip(axes[row],[rgb,sem,overlay,color,instance_overlay],['RGB','semantic label','RGB + label','class-colored mask','instance boundary']): ax.imshow(image,cmap='tab10' if image.ndim==2 else None,vmin=0 if image.ndim==2 else None,vmax=4 if image.ndim==2 else None); ax.axis('off'); ax.set_title(f'{title} / scene {index}',fontsize=7)
fig.tight_layout(); fig.savefig(OUT/'sample_alignment_examples.png',dpi=120); fig.savefig(OUT/'rgb_label_overlay_examples.png',dpi=120); plt.close(fig)
audit={'status':'SYSTEMATIC_RGB_LABEL_MISALIGNMENT_FOUND','audited_train_scene_ids':ids,'rgb_shape':list(data['images'].shape[1:]),'label_shape':list(data['semantic_masks'].shape[1:]),'shape_match':data['images'].shape[1:3]==data['semantic_masks'].shape[1:3],'vertical_or_horizontal_flip_observed':False,'resize_applied':False,'all_black_label_count':sum(black),'illegal_class_ids':illegal,'valid_class_ids':sorted(np.unique(data['semantic_masks'][ids]).tolist()),'image_label_index_match':True,'root_causes':['class-independent texture drawn over full bounding box without instance-mask clipping','ROBOT antenna drawn to RGB only without semantic/instance labels'],'affected_classes':['HUMAN','VEHICLE','ROBOT'],'minimal_fix':'clip all texture to current instance mask and label antenna consistently','diagnosis_sequence_stopped_after_alignment':True}
(OUT/'sample_alignment_audit.json').write_text(json.dumps(audit,indent=2)+'\n'); print(json.dumps(audit,indent=2))
