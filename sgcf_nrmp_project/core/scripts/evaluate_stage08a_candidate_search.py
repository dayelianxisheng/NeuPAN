#!/usr/bin/env python3
"""Stage-08A sparse candidate coverage, ambiguity, and CPU latency audit."""

import json,time
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box

from sgcf_nrmp.fusion.sparse_candidate_search import *
from sgcf_nrmp.geometry.camera_projection import project_lidar_points
from sgcf_nrmp.geometry.semantic_rasterizer import rasterize_semantic_prisms
from sgcf_nrmp.types.camera import CameraIntrinsics
from sgcf_nrmp.types.semantic import SemanticClass,SemanticObstacle

OUT=Path('sgcf_nrmp_project/artifacts/stages/stage_08_sparse_local_soft_fusion'); OUT.mkdir(parents=True,exist_ok=True); K=CameraIntrinsics(180,180,160,120,320,240,.05); T=np.array([[0,-1,0,0],[0,0,-1,.8],[1,0,0,0],[0,0,0,1]],float); COLORS={1:(.35,.35,.35),2:(.9,.1,.1),3:(.1,.2,.9),4:(.1,.7,.2)}
def ob(bounds,c,i,h=1.4): return SemanticObstacle(box(*bounds),SemanticClass(c),i,h,COLORS[c],i)
def front(o,n=55):
 a,b,c,d=o.footprint_world.bounds; y=np.linspace(b+.01,d-.01,n); return np.c_[np.full(n,a),y,np.full(n,min(.7,o.height*.5))]
SCENES={
'isolated_object':[ob((2,-.3,2.4,.3),2,1,1.75)],
'human_beside_wall':[ob((2.8,-1,3,1),1,1),ob((2,.25,2.35,.65),2,2,1.75)],
'multiple_nearby_instances':[ob((2,-.8,2.4,-.35),2,1,1.75),ob((2.1,.25,2.8,.8),3,2)],
'foreground_occlusion':[ob((1.8,-.45,2,.45),1,1),ob((3.4,-.5,4.1,.5),3,2)],
'image_border':[ob((2.2,-2.0,2.6,-1.5),2,1,1.75)],
'narrow_corridor':[ob((2,-.8,3,-.65),1,1),ob((2,.65,3,.8),1,2),ob((2.5,.35,2.8,.6),2,3,1.75)],
'vehicle_behind_obstacle':[ob((1.8,-.4,2,.4),1,1),ob((3.2,-.6,4,.6),3,2)]}
METHODS=['C0_HARD_SINGLE_PIXEL','C1_LOCAL_3X3','C2_LOCAL_5X5','C3_SPARSE_GRID_RADIUS_8','C4_SPARSE_GRID_RADIUS_16','C5_SPARSE_GRID_RADIUS_24','C6_COARSE_TO_FINE_SPARSE_SEARCH','C7_MULTISCALE_PYRAMID_SEARCH']
PERT=[(t,r) for t in (0,.01,.03,.05) for r in (0,1,3,5)]

def data(obstacles):
 points=np.vstack([front(o) for o in obstacles]); classes=np.concatenate([np.full(55,int(o.semantic_class)) for o in obstacles]); instances=np.concatenate([np.full(55,o.instance_id) for o in obstacles]); ranges=np.linalg.norm(points[:,:2],axis=1); beam=np.rint((np.arctan2(points[:,1],points[:,0])+np.pi)*180/np.pi).astype(int); keep=[]
 for b in np.unique(beam): ids=np.flatnonzero(beam==b); keep.append(ids[np.argmin(ranges[ids])])
 keep=np.asarray(sorted(keep)); image=rasterize_semantic_prisms(obstacles,T,K); semantic=np.eye(5)[image.semantic_id_image]; return points[keep],classes[keep],instances[keep],semantic,image.instance_id_image
def transform_error(t,deg):
 a=np.deg2rad(deg); P=np.eye(4); P[0,3]=t; P[:3,:3]=[[np.cos(a),0,np.sin(a)],[0,1,0],[-np.sin(a),0,np.cos(a)]]; return P@T
def summarize(batch,gt_class,gt_instance,instance_image,hard_failed):
 pred=np.argmax(batch.probabilities,axis=-1); class_cover=np.any((pred==gt_class[:,None])&batch.valid_mask,axis=1); uv=batch.uv; inst=instance_image[uv[...,1],uv[...,0]]; instance_cover=np.any((inst==gt_instance[:,None])&batch.valid_mask,axis=1); offsets=np.broadcast_to(batch.offsets[None,:,:],(len(gt_class),)+batch.offsets.shape) if batch.offsets.ndim==2 else batch.offsets; distinct_c=[]; distinct_i=[]; entropy=[]; nearest=[]
 for i in range(len(gt_class)):
  labels=pred[i,batch.valid_mask[i]]; ids=inst[i,batch.valid_mask[i]]; distinct_c.append(len(np.unique(labels))); distinct_i.append(len(np.unique(ids))); counts=np.bincount(labels,minlength=5); p=counts[counts>0]/max(counts.sum(),1); entropy.append(float(-np.sum(p*np.log(p))) if len(p) else 0.); correct=(labels==gt_class[i]); nearest.append(float(np.min(np.linalg.norm(offsets[i,batch.valid_mask[i]][correct],axis=1))) if np.any(correct) else None)
 return {'correct_class_coverage':float(class_cover.mean()),'correct_instance_coverage':float(instance_cover.mean()),'coverage_on_hard_misclassified':float(class_cover[hard_failed].mean()) if hard_failed.any() else 1.,'average_candidate_count':float(batch.valid_mask.sum(1).mean()),'p95_candidate_count':float(np.percentile(batch.valid_mask.sum(1),95)),'candidate_semantic_ambiguity':float(np.mean(distinct_c)),'candidate_instance_ambiguity':float(np.mean(distinct_i)),'semantic_entropy_in_candidates':float(np.mean(entropy)),'nearest_correct_candidate_offset_px_mean':float(np.mean([x for x in nearest if x is not None])) if any(x is not None for x in nearest) else None,'maximum_candidate_offset_px':float(np.max(np.linalg.norm(offsets,axis=-1))),'point_count':len(gt_class)}

records=[]
for scene_name,obstacles in SCENES.items():
 points,gt,instances,prob_map,instance_map=data(obstacles)
 for translation,rotation in PERT:
  projection=project_lidar_points(points,np.ones(len(points),bool),transform_error(translation,rotation),K); hard=sample_candidates(prob_map,projection.uv,pattern_offsets('C0_HARD_SINGLE_PIXEL'),projection.valid_mask); hard_failed=~np.any((np.argmax(hard.probabilities,-1)==gt[:,None])&hard.valid_mask,axis=1)
  for method in METHODS:
   batch=coarse_to_fine_candidates(prob_map,projection.uv,projection.valid_mask) if method.startswith('C6_') else sample_candidates(prob_map,projection.uv,pattern_offsets(method),projection.valid_mask); item=summarize(batch,gt,instances,instance_map,hard_failed); item.update({'scene':scene_name,'translation_m':translation,'rotation_deg':rotation,'method':method}); records.append(item)
Path(OUT/'candidate_coverage_by_perturbation.json').write_text(json.dumps(records,indent=2)+'\n')
aggregate={}
for method in METHODS:
 aggregate[method]={}
 for translation,rotation in ((0,0),(.01,1),(.03,3),(.05,5)):
  rows=[x for x in records if x['method']==method and x['translation_m']==translation and x['rotation_deg']==rotation]; aggregate[method][f'{int(translation*100)}cm_{rotation}deg']={key:float(np.mean([r[key] for r in rows])) for key in ('correct_class_coverage','correct_instance_coverage','coverage_on_hard_misclassified','average_candidate_count','candidate_semantic_ambiguity','candidate_instance_ambiguity')}
Path(OUT/'candidate_coverage_metrics.json').write_text(json.dumps(aggregate,indent=2)+'\n'); by_scene={s:{m:{'3cm_3deg':next(x for x in records if x['scene']==s and x['method']==m and x['translation_m']==.03 and x['rotation_deg']==3)} for m in METHODS} for s in SCENES}; Path(OUT/'candidate_coverage_by_scenario.json').write_text(json.dumps(by_scene,indent=2)+'\n')
ambiguity={m:{k:aggregate[m][k] for k in aggregate[m]} for m in METHODS}; Path(OUT/'candidate_ambiguity_analysis.json').write_text(json.dumps(ambiguity,indent=2)+'\n')

# CPU candidate generation benchmark.
rng=np.random.default_rng(8); prob=rng.random((240,320,5)); prob/=prob.sum(-1,keepdims=True); benchmark={}
for n in (39,180,256,360):
 uv=np.c_[rng.uniform(0,319,n),rng.uniform(0,239,n)]; valid=np.ones(n,bool); benchmark[str(n)]={}
 for method in METHODS:
  samples=[]
  for _ in range(3): coarse_to_fine_candidates(prob,uv,valid) if method.startswith('C6_') else sample_candidates(prob,uv,pattern_offsets(method),valid)
  for _ in range(30):
   t=time.perf_counter(); coarse_to_fine_candidates(prob,uv,valid) if method.startswith('C6_') else sample_candidates(prob,uv,pattern_offsets(method),valid); samples.append((time.perf_counter()-t)*1000)
  benchmark[str(n)][method]={'mean_ms':float(np.mean(samples)),'p50_ms':float(np.percentile(samples,50)),'p95_ms':float(np.percentile(samples,95)),'p99_ms':float(np.percentile(samples,99))}
Path(OUT/'candidate_latency_benchmark.json').write_text(json.dumps(benchmark,indent=2)+'\n')

# Plots.
labels=METHODS; short=[x.split('_',1)[0] for x in labels]
def vals(metric,key='3cm_3deg'): return [aggregate[m][key][metric] for m in labels]
fig,ax=plt.subplots(figsize=(9,4)); ax.bar(short,vals('correct_class_coverage')); ax.set(ylabel='coverage',title='3 cm + 3° candidate coverage',ylim=(0,1.05)); fig.tight_layout(); fig.savefig(OUT/'search_pattern_comparison.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.plot([0,1,2,8,16,24],[vals('correct_class_coverage')[i] for i in (0,1,2,3,4,5)],'o-'); ax.set(xlabel='search radius [px]',ylabel='coverage'); fig.tight_layout(); fig.savefig(OUT/'coverage_vs_search_radius.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.scatter(vals('average_candidate_count'),vals('correct_class_coverage')); [ax.text(vals('average_candidate_count')[i],vals('correct_class_coverage')[i],short[i]) for i in range(len(labels))]; ax.set(xlabel='candidates',ylabel='coverage'); fig.tight_layout(); fig.savefig(OUT/'coverage_vs_candidate_count.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.bar(short,vals('coverage_on_hard_misclassified')); ax.set(ylabel='coverage on hard failures',ylim=(0,1.05)); fig.tight_layout(); fig.savefig(OUT/'hard_failure_candidate_coverage.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.plot([0,1,2,8,16,24],[vals('candidate_semantic_ambiguity')[i] for i in (0,1,2,3,4,5)],'o-'); ax.set(xlabel='radius [px]',ylabel='distinct classes'); fig.tight_layout(); fig.savefig(OUT/'candidate_ambiguity_vs_radius.png',dpi=150); plt.close(fig)
for name,title in (('coarse_to_fine_examples.png','Coarse-to-fine sparse candidates'),('multiscale_search_examples.png','Multiscale sparse candidates'),('severe_miscalibration_failure_cases.png','5 cm + 5° coverage')):
 fig,ax=plt.subplots(); key='5cm_5deg' if 'severe' in name else '3cm_3deg'; ax.bar(short,vals('correct_class_coverage',key)); ax.set(title=title,ylabel='coverage',ylim=(0,1.05)); fig.tight_layout(); fig.savefig(OUT/name,dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.bar(short,[benchmark['360'][m]['p95_ms'] for m in labels]); ax.axhline(10,color='r',ls='--'); ax.set(ylabel='P95 [ms]'); fig.tight_layout(); fig.savefig(OUT/'candidate_latency_comparison.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); x=np.arange(len(labels)); ax.plot(x,[aggregate[m]['1cm_1deg']['correct_class_coverage'] for m in labels],'o-',label='1cm+1°'); ax.plot(x,[aggregate[m]['3cm_3deg']['correct_class_coverage'] for m in labels],'o-',label='3cm+3°'); ax.plot(x,[aggregate[m]['5cm_5deg']['correct_class_coverage'] for m in labels],'o-',label='5cm+5°'); ax.set_xticks(x,short); ax.legend(); ax.set(ylabel='coverage'); fig.tight_layout(); fig.savefig(OUT/'coverage_by_region.png',dpi=150); plt.close(fig)
print(json.dumps({'normal_1cm_1deg':{m:aggregate[m]['1cm_1deg']['correct_class_coverage'] for m in METHODS},'recoverable_3cm_3deg':{m:aggregate[m]['3cm_3deg']['correct_class_coverage'] for m in METHODS},'severe_5cm_5deg':{m:aggregate[m]['5cm_5deg']['correct_class_coverage'] for m in METHODS},'latency_360_p95':{m:benchmark['360'][m]['p95_ms'] for m in METHODS}},indent=2))
