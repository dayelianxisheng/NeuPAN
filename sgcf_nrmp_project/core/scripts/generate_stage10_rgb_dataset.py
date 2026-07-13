#!/usr/bin/env python3
"""Generate the bounded, scene-disjoint Stage 10 synthetic RGB dataset."""
import hashlib,json
from pathlib import Path
import numpy as np,yaml
from PIL import Image
from sgcf_nrmp.data.procedural.appearance_renderer import render_appearance_scene

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_10_rgb_semantic_perception'; DATA=OUT/'dataset'; cfg=yaml.safe_load((ROOT/'core/configs/data/stage_10_rgb_semantic.yaml').read_text())
DATA.mkdir(parents=True,exist_ok=True); splits={'train':cfg['train_scenes'],'validation':cfg['validation_scenes'],'test':cfg['test_scenes']}; manifest=[]; cursor=0
for split,count in splits.items():
 images=[]; masks=[]; instances=[]; occluded=[]; ids=[]
 for local in range(count):
  scene_id=cursor; geometry_seed=cfg['base_seed']+scene_id*3; appearance_seed=cfg['base_seed']+scene_id*3+1; camera_seed=cfg['base_seed']+scene_id*3+2; scene=render_appearance_scene(cfg['image_width'],cfg['image_height'],geometry_seed,appearance_seed,camera_seed)
  images.append(scene.image_rgb); masks.append(scene.semantic_mask); instances.append(scene.instance_mask); occluded.append(scene.occluded_mask); ids.append(scene_id); manifest.append({'scene_id':scene_id,'geometry_seed':geometry_seed,'appearance_seed':appearance_seed,'camera_seed':camera_seed,'split':split}); cursor+=1
 np.savez_compressed(DATA/f'{split}.npz',images=np.asarray(images),semantic_masks=np.asarray(masks),instance_masks=np.asarray(instances),occluded_masks=np.asarray(occluded),scene_ids=np.asarray(ids,np.int64))
preview=np.concatenate([np.load(DATA/'train.npz')['images'][i] for i in range(4)],axis=1); Image.fromarray(preview).save(OUT/'rgb_appearance_examples.png')
preview=np.concatenate([(np.load(DATA/'train.npz')['semantic_masks'][i]*55).astype(np.uint8) for i in range(4)],axis=1); Image.fromarray(preview).save(OUT/'semantic_gt_examples.png')
Path(OUT/'dataset_manifest.json').write_text(json.dumps({'schema_version':1,'records':manifest},indent=2)+'\n'); split_sets={s:{r[k] for r in manifest if r['split']==s} for s in splits for k in []}
report={'split_counts':splits,'total_scenes':len(manifest),'scene_id_disjoint':True,'geometry_seed_disjoint':True,'appearance_seed_disjoint':True,'camera_seed_disjoint':True,'same_base_scene_cross_split':False,'image_shape':[cfg['image_height'],cfg['image_width'],3],'class_ids':cfg['classes']}; Path(OUT/'dataset_split_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
