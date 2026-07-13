#!/usr/bin/env python3
"""One authorized 48-image gate recheck after the alignment fix; no full train."""
import hashlib,json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np,torch,yaml
from torch.utils.data import DataLoader,Subset
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all,train_epoch

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; cfg_path=ROOT/'core/configs/train/stage_10a_pipeline_diagnosis.yaml'; cfg=yaml.safe_load(cfg_path.read_text()); model_cfg=yaml.safe_load((ROOT/'core/configs/model/tiny_semantic_segmentation.yaml').read_text()); seed_all(cfg['seed']); torch.set_num_threads(4)
dataset=RGBSemanticDataset(OUT/'dataset/train.npz'); selected=cfg['selected_train_scene_ids']; index_by_id={int(v):i for i,v in enumerate(dataset.scene_ids)}; indices=[index_by_id[i] for i in selected]; subset=Subset(dataset,indices); loader=DataLoader(subset,batch_size=cfg['batch_size'],shuffle=True,generator=torch.Generator().manual_seed(cfg['seed']))
counts=np.bincount(dataset.masks[indices].ravel(),minlength=5); weights=np.sqrt(counts.sum()/np.maximum(counts,1)); weights/=weights.mean(); criterion=torch.nn.CrossEntropyLoss(weight=torch.tensor(weights,dtype=torch.float32)); model=TinySemanticSegmentation(model_cfg['class_count'],model_cfg['base_channels']); optimizer=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay']); history=[]
for epoch in range(cfg['maximum_diagnosis_epochs']): history.append(train_epoch(model,loader,optimizer,criterion))
@torch.no_grad()
def metrics():
 model.eval(); confusion=np.zeros((5,5),np.int64)
 for b in DataLoader(subset,batch_size=cfg['batch_size']):
  pred=model(b['image']).argmax(1).numpy(); target=b['target'].numpy()
  for t,p in zip(target.ravel(),pred.ravel()): confusion[t,p]+=1
 recall=np.diag(confusion)/np.maximum(confusion.sum(1),1); precision=np.diag(confusion)/np.maximum(confusion.sum(0),1); f1=2*precision*recall/np.maximum(precision+recall,1e-12)
 return float(np.trace(confusion)/confusion.sum()),float(np.mean(f1)),recall.tolist(),confusion.tolist()
accuracy,macro_f1,recall,confusion=metrics(); relative=history[-1]/history[0]; result={'initial_loss':history[0],'final_loss':history[-1],'relative_loss':relative,'required_relative_loss_strictly_below':cfg['required_relative_loss'],'pass':bool(relative<cfg['required_relative_loss']),'epochs':len(history),'selected_image_ids':selected,'selected_from_train_only':True,'config_hash_sha256':hashlib.sha256(cfg_path.read_bytes()).hexdigest(),'model_parameter_count':model.parameter_count,'training_pixel_accuracy':accuracy,'training_macro_f1':macro_f1,'per_class_recall':recall,'confusion_matrix':confusion,'minimal_fix':cfg['minimal_fix'],'augmentation':False,'dropout':False,'weight_decay':cfg['weight_decay']}
(OUT/'overfit_gate_recheck.json').write_text(json.dumps(result,indent=2)+'\n'); (OUT/'training_config.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False)); (OUT/'model_architecture.json').write_text(json.dumps({'name':'TinySemanticSegmentation','parameter_count':model.parameter_count,'class_count':5,'base_channels':model_cfg['base_channels'],'batch_normalization':False,'dropout':False,'pretrained':False},indent=2)+'\n')
before=json.loads((OUT/'overfit_gate.json').read_text()); fig,ax=plt.subplots(); ax.bar(['before','after'],[before['relative_loss'],relative]); ax.axhline(cfg['required_relative_loss'],color='red',ls='--'); ax.set(ylabel='final / initial loss',title='48-image overfit gate'); fig.tight_layout(); fig.savefig(OUT/'overfit_before_after.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.plot(np.arange(1,len(history)+1),history); ax.set(xlabel='epoch',ylabel='weighted CE',title='48-image gate recheck'); ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(OUT/'loss_component_curves.png',dpi=150); plt.close(fig)
print(json.dumps(result,indent=2))
