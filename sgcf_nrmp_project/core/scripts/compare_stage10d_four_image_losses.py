#!/usr/bin/env python3
"""Fair same-initialization four-image L0/L1 comparison and confusion audit."""
import hashlib,json,math
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np,torch,yaml
from scipy.ndimage import distance_transform_edt
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; cfg=yaml.safe_load((ROOT/'core/configs/train/stage_10d_four_image_diagnosis.yaml').read_text()); dataset=RGBSemanticDataset(OUT/'dataset/train.npz'); ids=cfg['selected_scene_ids']; images=torch.stack([dataset[i]['image'] for i in ids]); targets=torch.stack([dataset[i]['target'] for i in ids]); names=['UNKNOWN','STATIC_OBSTACLE','HUMAN','VEHICLE','ROBOT']; counts=np.bincount(dataset.masks[:48].ravel(),minlength=5); weights=np.sqrt(counts.sum()/np.maximum(counts,1)); weights/=weights.mean(); seed_all(cfg['seed']); torch.set_num_threads(4); template=TinySemanticSegmentation(); initial={k:v.detach().clone() for k,v in template.state_dict().items()}; initial_hash=hashlib.sha256(b''.join(v.numpy().tobytes() for v in initial.values())).hexdigest()
def metrics(logits):
 pred=logits.argmax(1); cm=np.bincount((targets*5+pred).numpy().ravel(),minlength=25).reshape(5,5); rec=np.diag(cm)/np.maximum(cm.sum(1),1); pre=np.diag(cm)/np.maximum(cm.sum(0),1); f1=2*pre*rec/np.maximum(pre+rec,1e-12); interiors=[]
 for mask in targets.numpy(): interiors.append(np.stack([distance_transform_edt(mask==c)>2 for c in range(5)]).any(0))
 interior=np.stack(interiors); flat_t=targets.numpy()[interior]; flat_p=pred.numpy()[interior]; icm=np.bincount(flat_t*5+flat_p,minlength=25).reshape(5,5); irec=np.diag(icm)/np.maximum(icm.sum(1),1)
 return pred.numpy(),{'pixel_accuracy':float(np.trace(cm)/cm.sum()),'macro_f1':float(np.mean(f1)),'per_class_recall':dict(zip(names,rec.tolist())),'prediction_fraction':dict(zip(names,(cm.sum(0)/cm.sum()).tolist())),'confusion_matrix':cm.tolist(),'interior_pixel_accuracy':float(np.trace(icm)/max(icm.sum(),1)),'interior_per_class_recall':dict(zip(names,irec.tolist()))}
def run(weighted):
 model=TinySemanticSegmentation(); model.load_state_dict(initial); criterion=torch.nn.CrossEntropyLoss(weight=torch.tensor(weights,dtype=torch.float32) if weighted else None); opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=0.); records=[]; snapshots={}; last_grad=0.
 for step in range(cfg['steps']+1):
  model.eval()
  with torch.no_grad(): logits=model(images); loss=float(criterion(logits,targets)); pred,met=metrics(logits)
  if step%100==0: records.append({'step':step,'loss':loss,'gradient_norm_last_step':last_grad,**met}); snapshots[str(step)]=pred.copy()
  if step==cfg['steps']: break
  model.train(); opt.zero_grad(set_to_none=True); value=criterion(model(images),targets); value.backward(); last_grad=math.sqrt(sum(float(p.grad.detach().norm())**2 for p in model.parameters() if p.grad is not None)); opt.step()
 final=records[-1]; relative=final['loss']/records[0]['loss']; recalls=final['per_class_recall']; passed=relative<=.10 and final['pixel_accuracy']>=.97 and final['macro_f1']>=.90 and min(recalls[n] for n in names[1:])>=.90 and recalls['UNKNOWN']>=.95
 return model,records,snapshots,{'initial_state_sha256':initial_hash,'steps':cfg['steps'],'initial_loss':records[0]['loss'],'final_loss':final['loss'],'relative_loss':relative,**{k:v for k,v in final.items() if k not in ('step','loss')},'pass':passed,'records':records}
u_model,u_records,u_snaps,u_result=run(False); w_model,w_records,w_snaps,w_result=run(True)
(OUT/'four_image_unweighted_ce.json').write_text(json.dumps(u_result,indent=2)+'\n'); (OUT/'four_image_weighted_ce.json').write_text(json.dumps(w_result,indent=2)+'\n')
comparison={'selected_scene_ids':ids,'same_initialization':u_result['initial_state_sha256']==w_result['initial_state_sha256'],'same_steps':u_result['steps']==w_result['steps'],'same_optimizer_and_learning_rate':True,'L0_unweighted_CE':{k:v for k,v in u_result.items() if k!='records'},'L1_current_weighted_CE':{k:v for k,v in w_result.items() if k!='records'}}; (OUT/'four_image_loss_comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
# HUMAN/ROBOT probability and confusion, including interior/boundary aggregate.
def hr(model):
 model.eval()
 with torch.no_grad(): prob=model(images).softmax(1).numpy(); pred=prob.argmax(1)
 result={}
 for c,name in ((2,'HUMAN'),(4,'ROBOT')):
  gt=targets.numpy()==c; boundary=np.stack([(m==c)&(distance_transform_edt(m==c)<=2) for m in targets.numpy()]); interior=gt&~boundary
  def region(region):
   vals=np.bincount(pred[region],minlength=5); return {'pixel_count':int(region.sum()),'prediction_distribution':dict(zip(names,(vals/max(vals.sum(),1)).tolist())),'mean_HUMAN_probability':float(prob[:,2][region].mean()) if region.any() else 0.,'mean_ROBOT_probability':float(prob[:,4][region].mean()) if region.any() else 0.}
  result[name]={'all':region(gt),'interior':region(interior),'boundary':region(boundary)}
 return result,pred
u_hr,u_pred=hr(u_model); w_hr,w_pred=hr(w_model); confusion={'L0_unweighted_CE':u_hr,'L1_current_weighted_CE':w_hr,'unweighted_reduces_bidirectional_confusion':u_hr['HUMAN']['all']['prediction_distribution']['ROBOT']+u_hr['ROBOT']['all']['prediction_distribution']['HUMAN'] < w_hr['HUMAN']['all']['prediction_distribution']['ROBOT']+w_hr['ROBOT']['all']['prediction_distribution']['HUMAN']}; (OUT/'human_robot_confusion_stage10d.json').write_text(json.dumps(confusion,indent=2)+'\n')
# Curves and prediction figures.
fig,ax=plt.subplots(); ax.plot([r['step'] for r in u_records],[r['loss'] for r in u_records],label='L0 unweighted'); ax.plot([r['step'] for r in w_records],[r['loss'] for r in w_records],label='L1 weighted'); ax.set(xlabel='step',ylabel='CE loss'); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'four_image_loss_comparison.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4)); x=np.arange(5); ax.bar(x-.18,list(u_result['per_class_recall'].values()),.36,label='L0'); ax.bar(x+.18,list(w_result['per_class_recall'].values()),.36,label='L1'); ax.axhline(.9,color='red',ls='--'); ax.set_xticks(x,names); ax.set_ylim(0,1.05); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'four_image_per_class_recall.png',dpi=150); plt.close(fig)
def progress(snaps,name):
 fig,axes=plt.subplots(3,4,figsize=(10,7))
 for row,step in enumerate(('0','600','1200')):
  for col in range(4): axes[row,col].imshow(snaps[step][col],vmin=0,vmax=4,cmap='tab10'); axes[row,col].axis('off'); axes[row,col].set_title(f'scene {ids[col]} step {step}',fontsize=7)
 fig.tight_layout(); fig.savefig(OUT/name,dpi=140); plt.close(fig)
progress(u_snaps,'four_image_prediction_progress_unweighted.png'); progress(w_snaps,'four_image_prediction_progress_weighted.png')
fig,axes=plt.subplots(2,4,figsize=(11,6));
for col,i in enumerate(ids): axes[0,col].imshow(dataset.images[i]); axes[0,col].contour(dataset.masks[i]==2,colors='red'); axes[0,col].contour(dataset.masks[i]==4,colors='lime'); axes[1,col].imshow(u_pred[col],vmin=0,vmax=4,cmap='tab10'); axes[1,col].contour(dataset.masks[i]==2,colors='red'); axes[1,col].contour(dataset.masks[i]==4,colors='lime');
for ax in axes.ravel(): ax.axis('off')
fig.tight_layout(); fig.savefig(OUT/'human_robot_confusion_examples_stage10d.png',dpi=140); plt.close(fig)
# Comparison result doubles as authoritative recheck; no seed rerun.
selected='L0_unweighted_CE' if u_result['pass'] and (not w_result['pass'] or u_result['macro_f1']>=w_result['macro_f1']) else ('L1_current_weighted_CE' if w_result['pass'] else None); recheck={'authoritative_four_image_recheck':selected,'reused_fair_comparison_result':True,'additional_training_run':False,'L0_pass':u_result['pass'],'L1_pass':w_result['pass'],'selected_default_loss':'unweighted_cross_entropy' if selected=='L0_unweighted_CE' else ('current_weighted_cross_entropy' if selected else None),'ready_for_48_image_overfit_recheck':selected is not None}; (OUT/'four_image_recheck_stage10d.json').write_text(json.dumps(recheck,indent=2)+'\n')
print(json.dumps({'comparison':comparison,'confusion':confusion,'recheck':recheck},indent=2))
