#!/usr/bin/env python3
"""Stage 10C frozen-scene residual, sanity, and bounded convergence audit."""
import hashlib,json,math
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np,torch
from scipy.ndimage import distance_transform_edt,uniform_filter
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; dataset=RGBSemanticDataset(OUT/'dataset/train.npz'); raw=np.load(OUT/'dataset/train.npz'); image=dataset[0]['image'][None]; target=dataset[0]['target'][None]; rgb=raw['images'][0]; mask=raw['semantic_masks'][0]; instances=raw['instance_masks'][0]; occluded=raw['occluded_masks'][0]; names=['UNKNOWN','STATIC_OBSTACLE','HUMAN','VEHICLE','ROBOT']; counts=np.bincount(dataset.masks[:48].ravel(),minlength=5); weights=np.sqrt(counts.sum()/np.maximum(counts,1)); weights/=weights.mean(); weights_t=torch.tensor(weights,dtype=torch.float32); criterion=torch.nn.CrossEntropyLoss(weight=weights_t); torch.set_num_threads(4)
manifest=json.loads((OUT/'dataset_manifest.json').read_text()); record=next(x for x in manifest['records'] if x['scene_id']==0); frozen={'scene_id':0,'image_id':0,'geometry_seed':record['geometry_seed'],'appearance_seed':record['appearance_seed'],'camera_seed':record['camera_seed'],'rgb_sha256':hashlib.sha256(rgb.tobytes()).hexdigest(),'semantic_label_sha256':hashlib.sha256(mask.tobytes()).hexdigest()}
def metrics(logits):
 pred=logits.argmax(1); cm=np.bincount((target*5+pred).numpy().ravel(),minlength=25).reshape(5,5); recall=np.diag(cm)/np.maximum(cm.sum(1),1); precision=np.diag(cm)/np.maximum(cm.sum(0),1); f1=2*precision*recall/np.maximum(precision+recall,1e-12); return pred[0].numpy(),{'pixel_accuracy':float(np.trace(cm)/cm.sum()),'macro_f1':float(np.mean(f1)),'per_class_recall':dict(zip(names,recall.tolist())),'confusion_matrix':cm.tolist(),'prediction_fraction':dict(zip(names,(cm.sum(0)/cm.sum()).tolist()))}
def train(steps,weighted=True,seed=10,record_every=50):
 seed_all(seed); model=TinySemanticSegmentation(); opt=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=0.); ce=criterion if weighted else torch.nn.CrossEntropyLoss(); history=[]; snapshots={}
 for step in range(steps+1):
  model.eval()
  with torch.no_grad(): logits=model(image); loss=float(ce(logits,target)); _,met=metrics(logits)
  if step%record_every==0 or step==steps: history.append({'step':step,'loss':loss,**met})
  if step in (0,80,steps): snapshots[str(step)]=logits.detach().clone()
  if step==steps: break
  model.train(); opt.zero_grad(set_to_none=True); loss_t=ce(model(image),target); loss_t.backward(); opt.step()
 return model,history,snapshots
# Reconstruct exact Stage 10B 80-step residual state.
model,old_history,old_snaps=train(80,True); old_logits=old_snaps['80']; pred,old_metrics=metrics(old_logits); prob=old_logits.softmax(1)[0].numpy(); error=pred!=mask; foreground=mask>0; boundary=(distance_transform_edt(foreground)<=3)&(distance_transform_edt(~foreground)<=3); semantic_boundary=np.zeros_like(mask,bool); semantic_boundary[1:]|=mask[1:]!=mask[:-1]; semantic_boundary[:,1:]|=mask[:,1:]!=mask[:,:-1]; boundary=distance_transform_edt(~semantic_boundary)<=3; interior=~boundary
def rate(region): return {'pixel_count':int(region.sum()),'error_count':int((error&region).sum()),'error_rate':float((error&region).sum()/max(region.sum(),1))}
by_gt={n:rate(mask==c) for c,n in enumerate(names)}; by_pred={n:rate(pred==c) for c,n in enumerate(names)}; radii={str(r):rate(distance_transform_edt(~semantic_boundary)<=r) for r in (1,2,3,5)}; robot_conf=np.bincount(pred[mask==4],minlength=5); robot_break=dict(zip(names,robot_conf.tolist()))
image_border=np.zeros_like(mask,bool); image_border[:5]=image_border[-5:]=True; image_border[:,:5]=True; image_border[:,-5:]=True
residual={'frozen_sample':frozen,'correct_pixel_count':int((~error).sum()),'incorrect_pixel_count':int(error.sum()),'error_rate_by_gt_class':by_gt,'error_rate_by_predicted_class':by_pred,'gt_unknown_predicted_foreground':int(np.sum((mask==0)&(pred!=0))),'gt_foreground_predicted_unknown':int(np.sum((mask!=0)&(pred==0))),'gt_robot_prediction_breakdown':robot_break,'error_by_boundary_radius_px':radii,'component_interior':rate(interior&foreground),'image_border_5px':rate(image_border)}; (OUT/'single_image_residual_error.json').write_text(json.dumps(residual,indent=2)+'\n')
# ROBOT regions are offline diagnostic masks only and never alter formal labels.
yy,xx=np.where(mask==4); x0,x1,y0,y1=xx.min(),xx.max(),yy.min(),yy.max(); h=y1-y0+1; robot=mask==4; rb=semantic_boundary&robot; ri=robot&(distance_transform_edt(robot)>2); antenna=robot&(np.indices(mask.shape)[0]<=y0+max(2,int(.18*h))); upper=robot&(np.indices(mask.shape)[0]<=y0+int(.55*h))&~antenna; body=robot&~upper&~antenna
def region_prediction(region):
 vals=np.bincount(pred[region],minlength=5); return {**rate(region),'recall_robot':float(np.mean(pred[region]==4)) if region.any() else 0.,'prediction_distribution':dict(zip(names,(vals/max(vals.sum(),1)).tolist())),'mean_robot_probability':float(prob[4][region].mean()) if region.any() else 0.,'mean_winning_probability':float(prob[:,region].max(0).mean()) if region.any() else 0.}
robot_regions={'main_body':region_prediction(body),'upper_structure':region_prediction(upper),'antenna':region_prediction(antenna),'boundary':region_prediction(rb),'interior':region_prediction(ri)}; (OUT/'robot_region_error_audit.json').write_text(json.dumps({'frozen_sample':frozen,'regions':robot_regions,'dominant_robot_misprediction':names[int(np.argmax(robot_conf[:4]))]},indent=2)+'\n')
# UNKNOWN diagnostic regions.
unknown=mask==0; object_exterior=unknown&(distance_transform_edt(foreground)<=3); border=np.zeros_like(mask,bool); border[:5]=border[-5:]=True; border[:,:5]=True; border[:,-5:]=True; local_var=uniform_filter(rgb.astype(float).var(2),3); texture=unknown&(local_var>np.percentile(local_var[unknown],75)); pure=unknown&~object_exterior&~occluded&~border; unknown_regions={'pure_background_interior':region_prediction(pure),'object_boundary_exterior':region_prediction(object_exterior),'occlusion_gap':region_prediction(unknown&occluded),'image_border':region_prediction(unknown&border),'texture_noise_region':region_prediction(texture)}; (OUT/'unknown_region_error_audit.json').write_text(json.dumps({'unknown_roles':['background','occlusion','invalid/unlabeled'],'regions':unknown_regions},indent=2)+'\n')
# Local 5x5 quantized RGB ambiguity on train scene 0 only.
quant=(rgb//32).astype(np.uint8); buckets=defaultdict(lambda:np.zeros(5,np.int64)); pad=np.pad(quant,((2,2),(2,2),(0,0)),mode='edge')
for y in range(mask.shape[0]):
 for x in range(mask.shape[1]): buckets[pad[y:y+5,x:x+5].tobytes()][mask[y,x]]+=1
ambiguous=[v for v in buckets.values() if np.count_nonzero(v)>1]; ambiguous_pixels=sum(v.sum() for v in ambiguous); ambiguity={'scene_id':0,'patch_size':5,'quantization_bin_width':32,'unique_patch_hash_count':len(buckets),'ambiguous_patch_hash_count':len(ambiguous),'pixels_with_ambiguous_hash':int(ambiguous_pixels),'ambiguous_pixel_fraction':float(ambiguous_pixels/mask.size),'large_ambiguity_threshold':.25,'large_ambiguity':bool(ambiguous_pixels/mask.size>=.25),'uses_train_only':True}; (OUT/'local_patch_label_ambiguity.json').write_text(json.dumps(ambiguity,indent=2)+'\n')
consistency={'frozen_sample':frozen,'foreground_rgb_without_label_after_fix':'not observed by renderer construction','foreground_label_without_visible_rgb_structure':'not observed in overlay audit','rgb_antialiasing_enabled':False,'rgb_blur_only':True,'hard_label_blur_mismatch_possible_near_boundary':True,'texture_clipped_to_instance':True,'shadow_rendering':False,'patch_ambiguity_reference':'local_patch_label_ambiguity.json'}; (OUT/'rgb_label_local_consistency.json').write_text(json.dumps(consistency,indent=2)+'\n')
# Identity metric sanity.
perfect=torch.full((1,5,*mask.shape),-12.); perfect.scatter_(1,target[:,None],12.); _,perfect_metrics=metrics(perfect); identity={'pixel_accuracy':perfect_metrics['pixel_accuracy'],'macro_f1':perfect_metrics['macro_f1'],'per_class_recall':perfect_metrics['per_class_recall'],'pass':perfect_metrics['pixel_accuracy']==1 and perfect_metrics['macro_f1']==1 and all(x==1 for x in perfect_metrics['per_class_recall'].values())}; (OUT/'metric_identity_sanity.json').write_text(json.dumps(identity,indent=2)+'\n')
if not identity['pass']: raise SystemExit('BLOCKED_LOSS_OR_METRIC_IMPLEMENTATION: identity metric failed')
# Direct-logits optimizer sanity.
seed_all(10); direct=torch.nn.Parameter(torch.zeros((1,5,*mask.shape))); opt=torch.optim.Adam([direct],lr=.5); curve=[]
for step in range(101):
 loss=criterion(direct,target)
 if step%10==0 or step==100: _,met=metrics(direct.detach()); curve.append({'step':step,'loss':float(loss.detach()),**met})
 if step<100: opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
direct_result={'initial_loss':curve[0]['loss'],'final_loss':curve[-1]['loss'],'relative_loss':curve[-1]['loss']/curve[0]['loss'],'pixel_accuracy':curve[-1]['pixel_accuracy'],'macro_f1':curve[-1]['macro_f1'],'per_class_recall':curve[-1]['per_class_recall'],'curve':curve,'pass':curve[-1]['pixel_accuracy']>.999 and min(curve[-1]['per_class_recall'].values())>.999}; (OUT/'direct_logits_sanity.json').write_text(json.dumps(direct_result,indent=2)+'\n')
fig,ax=plt.subplots(); ax.plot([x['step'] for x in curve],[x['loss'] for x in curve]); ax.set(xlabel='step',ylabel='weighted CE',title='Direct-logits sanity'); ax.grid(); fig.tight_layout(); fig.savefig(OUT/'direct_logits_loss_curve.png',dpi=150); plt.close(fig)
if not direct_result['pass']: raise SystemExit('BLOCKED_LOSS_OR_METRIC_IMPLEMENTATION: direct logits failed')
# Residual visualizations.
fig,axes=plt.subplots(1,4,figsize=(14,3)); axes[0].imshow(rgb); axes[1].imshow(mask,vmin=0,vmax=4,cmap='tab10'); axes[2].imshow(pred,vmin=0,vmax=4,cmap='tab10'); axes[3].imshow(error,cmap='Reds');
for ax,t in zip(axes,['RGB','GT','prediction','error']): ax.axis('off'); ax.set_title(t)
fig.tight_layout(); fig.savefig(OUT/'single_image_error_map.png',dpi=150); plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(10,3)); axes[0].imshow(rgb); axes[0].contour(semantic_boundary,colors='yellow'); axes[1].imshow(error&boundary,cmap='Reds'); axes[2].imshow(error&interior,cmap='Reds');
for ax,t in zip(axes,['semantic boundary','boundary errors','interior errors']): ax.axis('off'); ax.set_title(t)
fig.tight_layout(); fig.savefig(OUT/'single_image_boundary_error.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.bar(names,robot_conf); ax.set(ylabel='ROBOT GT pixels',title='ROBOT prediction breakdown'); fig.tight_layout(); fig.savefig(OUT/'robot_error_breakdown.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.bar(list(unknown_regions),[v['error_rate'] for v in unknown_regions.values()]); ax.tick_params(axis='x',rotation=25); ax.set(ylabel='error rate',title='UNKNOWN region errors'); fig.tight_layout(); fig.savefig(OUT/'unknown_error_breakdown.png',dpi=150); plt.close(fig)
print(json.dumps({'frozen':frozen,'residual':residual,'robot':robot_regions,'ambiguity':ambiguity,'metric_identity':identity,'direct_logits':{k:v for k,v in direct_result.items() if k!='curve'}},indent=2))
if ambiguity['large_ambiguity']: raise SystemExit('BLOCKED_VISUAL_IDENTIFIABILITY: local patch ambiguity exceeds threshold')
