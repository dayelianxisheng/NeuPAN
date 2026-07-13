#!/usr/bin/env python3
"""One final same-scene recheck after selecting finite optimization steps."""
import hashlib,json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np,torch,yaml
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; cfg_path=ROOT/'core/configs/train/stage_10c_single_image_recheck.yaml'; cfg=yaml.safe_load(cfg_path.read_text()); dataset=RGBSemanticDataset(OUT/'dataset/train.npz'); image=dataset[0]['image'][None]; target=dataset[0]['target'][None]; names=['UNKNOWN','STATIC_OBSTACLE','HUMAN','VEHICLE','ROBOT']; counts=np.bincount(dataset.masks[:48].ravel(),minlength=5); weights=np.sqrt(counts.sum()/np.maximum(counts,1)); weights/=weights.mean(); seed_all(cfg['seed']); torch.set_num_threads(4); model=TinySemanticSegmentation(); criterion=torch.nn.CrossEntropyLoss(weight=torch.tensor(weights,dtype=torch.float32)); opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay']); records=[]
def metrics(logits):
 pred=logits.argmax(1); cm=np.bincount((target*5+pred).numpy().ravel(),minlength=25).reshape(5,5); rec=np.diag(cm)/np.maximum(cm.sum(1),1); pre=np.diag(cm)/np.maximum(cm.sum(0),1); f1=2*pre*rec/np.maximum(pre+rec,1e-12); return {'pixel_accuracy':float(np.trace(cm)/cm.sum()),'macro_f1':float(np.mean(f1)),'per_class_recall':dict(zip(names,rec.tolist())),'prediction_fraction':dict(zip(names,(cm.sum(0)/cm.sum()).tolist())),'confusion_matrix':cm.tolist()}
for step in range(cfg['steps']+1):
 model.eval()
 with torch.no_grad(): logits=model(image); loss=float(criterion(logits,target)); met=metrics(logits)
 if step%100==0: records.append({'step':step,'loss':loss,**met})
 if step==cfg['steps']: break
 model.train(); opt.zero_grad(set_to_none=True); value=criterion(model(image),target); value.backward(); opt.step()
final=records[-1]; relative=final['loss']/records[0]['loss']; recalls=final['per_class_recall']; passed=relative<=.10 and final['pixel_accuracy']>=.98 and final['macro_f1']>=.95 and min(recalls.values())>=.95
result={'scene_id':0,'rgb_sha256':hashlib.sha256(dataset.images[0].tobytes()).hexdigest(),'semantic_label_sha256':hashlib.sha256(dataset.masks[0].tobytes()).hexdigest(),'initial_loss':records[0]['loss'],'final_loss':final['loss'],'relative_loss':relative,'pixel_accuracy':final['pixel_accuracy'],'macro_f1':final['macro_f1'],'per_class_recall':recalls,'prediction_fraction':final['prediction_fraction'],'epochs':None,'optimizer_steps':cfg['steps'],'model_parameter_count':model.parameter_count,'config_hash_sha256':hashlib.sha256(cfg_path.read_bytes()).hexdigest(),'selected_minimal_fix':cfg['selected_minimal_fix'],'pass':passed,'records':records}; (OUT/'single_image_recheck_stage10c.json').write_text(json.dumps(result,indent=2)+'\n')
fig,ax=plt.subplots(); ax.plot([r['step'] for r in records],[r['loss'] for r in records]); ax.axhline(records[0]['loss']*.1,color='red',ls='--',label='10% initial'); ax.set(xlabel='optimizer step',ylabel='weighted CE',title='Stage 10C final single-image recheck'); ax.grid(); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'single_image_recheck_curve_stage10c.png',dpi=150); plt.close(fig)
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
