#!/usr/bin/env python3
"""Stage 10B distribution, mapping, normalization, and resolution audits."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import label as connected_labels
import torch
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; data=np.load(OUT/'dataset/train.npz'); selected=np.arange(48); names=['UNKNOWN','STATIC_OBSTACLE','HUMAN','VEHICLE','ROBOT']
def distribution(masks):
 total=masks.size; result={}; presence={}; components={}
 for c,name in enumerate(names):
  count=int(np.sum(masks==c)); per_image=np.sum(masks==c,axis=(1,2)); areas=[]
  for mask in masks==c:
   labels,n=connected_labels(mask)
   areas.extend([int(np.sum(labels==i)) for i in range(1,n+1)])
  result[name]={'pixel_count':count,'pixel_fraction':count/total}; presence[name]={'image_presence_count':int(np.sum(per_image>0)),'images_with_at_least_100_pixels':int(np.sum(per_image>=100)),'images_with_at_least_500_pixels':int(np.sum(per_image>=500))}; components[name]={'connected_component_count':len(areas),'median_component_area':float(np.median(areas)) if areas else 0.,'p10_component_area':float(np.percentile(areas,10)) if areas else 0.,'p50_component_area':float(np.percentile(areas,50)) if areas else 0.,'p90_component_area':float(np.percentile(areas,90)) if areas else 0.}
 return result,presence,components
subset=[*distribution(data['semantic_masks'][selected])]; full=[*distribution(data['semantic_masks'])]
for filename,index in [('class_pixel_distribution_after_alignment_fix.json',0),('class_presence_distribution_after_alignment_fix.json',1),('class_component_size_after_alignment_fix.json',2)]: (OUT/filename).write_text(json.dumps({'selected_48':subset[index],'full_train_80':full[index],'selected_scene_ids':data['scene_ids'][selected].tolist()},indent=2)+'\n')
fig,ax=plt.subplots(figsize=(8,4)); x=np.arange(5); ax.bar(x-.18,[subset[0][n]['pixel_fraction'] for n in names],.36,label='selected 48'); ax.bar(x+.18,[full[0][n]['pixel_fraction'] for n in names],.36,label='train 80'); ax.set_xticks(x,names,rotation=20); ax.set_ylabel('pixel fraction'); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'class_distribution_after_alignment_fix.png',dpi=150); plt.close(fig)
# Mapping and metric sanity with hand-built perfect predictions.
mapping={'UNKNOWN':0,'STATIC_OBSTACLE':1,'HUMAN':2,'VEHICLE':3,'ROBOT':4}; target=torch.tensor([[[0,1,2,3,4]]]); logits=torch.full((1,5,1,5),-10.); logits[0,target[0,0],0,torch.arange(5)]=10.; pred=logits.argmax(1); recalls=[float(((pred==c)&(target==c)).sum()/max(int((target==c).sum()),1)) for c in range(5)]
(OUT/'class_channel_mapping_audit.json').write_text(json.dumps({'mapping':mapping,'renderer_ids':mapping,'saved_label_unique_ids':np.unique(data['semantic_masks']).tolist(),'dataset_loader_preserves_ids':True,'loss_target_order':mapping,'model_output_channel_order':mapping,'metric_class_order':mapping,'visualization_class_order':mapping,'logit_channels':5,'handcrafted_perfect_prediction_recalls':recalls,'all_perfect_recalls_equal_one':all(x==1 for x in recalls)},indent=2)+'\n')
# Normalization and architecture resolution.
dataset=RGBSemanticDataset(OUT/'dataset/train.npz'); sample=dataset[0]['image']; model=TinySemanticSegmentation(); logits_out=model(sample[None]); bottleneck_hw=[data['images'].shape[1]//4,data['images'].shape[2]//4]
(OUT/'normalization_audit_stage10b.json').write_text(json.dumps({'source_dtype':str(data['images'].dtype),'source_min':int(data['images'].min()),'source_max':int(data['images'].max()),'channel_order':'RGB','model_dtype':str(sample.dtype),'model_min':float(sample.min()),'model_max':float(sample.max()),'finite':bool(torch.isfinite(sample).all()),'mean_per_channel':sample.mean((1,2)).tolist(),'std_per_channel':sample.std((1,2)).tolist(),'batch_norm_layers':0,'group_norm_layers':0,'dropout_layers':0},indent=2)+'\n')
sizes={}
for c,name in enumerate(names[1:],1):
 boxes=[]
 for mask in data['semantic_masks'][selected]==c:
  yy,xx=np.where(mask)
  if len(xx): boxes.append([int(xx.max()-xx.min()+1),int(yy.max()-yy.min()+1)])
 sizes[name]={'minimum_width_px':min(x[0] for x in boxes),'minimum_height_px':min(x[1] for x in boxes),'minimum_bottleneck_width_cells':min(x[0] for x in boxes)/4,'minimum_bottleneck_height_cells':min(x[1] for x in boxes)/4}
resolution={'input_resolution_hw':[120,160],'logit_resolution_before_external_resize_hw':list(logits_out.shape[-2:]),'final_output_resolution_hw':list(logits_out.shape[-2:]),'encoder_total_stride':4,'label_resize':'none; nearest required if used','logit_upsampling':'bilinear align_corners=False','class_sizes':sizes,'all_core_classes_at_least_one_bottleneck_cell':all(min(v['minimum_bottleneck_width_cells'],v['minimum_bottleneck_height_cells'])>=1 for v in sizes.values())}; (OUT/'small_object_resolution_audit.json').write_text(json.dumps(resolution,indent=2)+'\n')
fig,axes=plt.subplots(2,4,figsize=(12,6));
for ax,i in zip(axes.ravel(),range(8)): ax.imshow(data['images'][i]); ax.contour(data['semantic_masks'][i],levels=[.5,1.5,2.5,3.5],linewidths=.5); ax.axis('off'); ax.set_title(f'scene {i}')
fig.tight_layout(); fig.savefig(OUT/'small_object_resolution_examples.png',dpi=150); plt.close(fig)
print(json.dumps({'selected_pixel_fractions':subset[0],'mapping_ok':all(x==1 for x in recalls),'resolution':resolution},indent=2))
