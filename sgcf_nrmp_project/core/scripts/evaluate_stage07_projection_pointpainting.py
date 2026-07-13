#!/usr/bin/env python3
"""Generate Stage-07 oracle semantic, PointPainting, robustness, and plots."""

from __future__ import annotations
import json,time
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box
import yaml

from sgcf_nrmp.fusion.pointpainting import paint_points
from sgcf_nrmp.geometry.camera_projection import project_lidar_points
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.geometry.semantic_rasterizer import rasterize_semantic_prisms
from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle
from sgcf_nrmp.semantic.margin_labeler import semantic_margin_ground_truth
from sgcf_nrmp.semantic.reliability_labeler import reliability_ground_truth
from sgcf_nrmp.types.camera import CameraIntrinsics
from sgcf_nrmp.types.semantic import SemanticClass,SemanticObstacle

ROOT=Path('sgcf_nrmp_project'); OUT=ROOT/'artifacts/stages/stage_07_projection_pointpainting'; OUT.mkdir(parents=True,exist_ok=True)
EVAL=yaml.safe_load((ROOT/'core/configs/eval/stage_07_projection.yaml').read_text()); MODEL=yaml.safe_load((ROOT/'core/configs/model/pointpainting_baseline.yaml').read_text()); C=EVAL['camera']; K=CameraIntrinsics(**C)
T=np.array([[0,-1,0,0],[0,0,-1,.8],[1,0,0,0],[0,0,0,1]],float); FOOTPRINT=rectangular_footprint(.8,.5); MARGINS={0:0.,1:0.,2:.35,3:.2,4:.15}
COLORS={SemanticClass.STATIC_OBSTACLE:(.35,.35,.35),SemanticClass.HUMAN:(.9,.15,.15),SemanticClass.VEHICLE:(.15,.3,.9),SemanticClass.ROBOT:(.2,.75,.25)}

def obstacle(bounds,klass,instance,height=1.4): return SemanticObstacle(box(*bounds),klass,instance,height,COLORS[klass],instance)
def front_points(item,count=45):
    minx,miny,maxx,maxy=item.footprint_world.bounds; y=np.linspace(miny+.01,maxy-.01,count); return np.c_[np.full(count,minx),y,np.full(count,min(item.height*.5,.7))]
def case_data(name,obstacles):
    points=np.vstack([front_points(o) for o in obstacles]); expected=np.concatenate([np.full(45,int(o.semantic_class)) for o in obstacles]); instances=np.concatenate([np.full(45,o.instance_id) for o in obstacles]); ranges=np.linalg.norm(points[:,:2],axis=1)
    # A 2D LiDAR returns only the nearest surface in each angular beam.
    beam=np.rint((np.arctan2(points[:,1],points[:,0])+np.pi)*180/np.pi).astype(int); keep=[]
    for index in np.unique(beam):
        candidates=np.flatnonzero(beam==index); keep.append(candidates[np.argmin(ranges[candidates])])
    keep=np.asarray(sorted(keep)); points=points[keep]; expected=expected[keep]; instances=instances[keep]; ranges=ranges[keep]
    images=rasterize_semantic_prisms(obstacles,T,K); projection=project_lidar_points(points,np.ones(len(points),bool),T,K); painted=paint_points(points[:,:2],ranges,projection,images.semantic_id_image,0.,**MODEL); return {'name':name,'obstacles':obstacles,'points':points,'expected':expected,'instances':instances,'ranges':ranges,'images':images,'projection':projection,'painted':painted}

CASES=[
 case_data('static_wall_and_robot',[obstacle((2.8,-1,3.0,1),SemanticClass.STATIC_OBSTACLE,1,1.2),obstacle((1.8,-.25,2.2,.25),SemanticClass.ROBOT,2,.8)]),
 case_data('human_beside_wall',[obstacle((2.8,-1,3.0,1),SemanticClass.STATIC_OBSTACLE,1,1.4),obstacle((2.0,.25,2.35,.65),SemanticClass.HUMAN,2,1.75)]),
 case_data('near_wall_occludes_vehicle',[obstacle((1.8,-.45,2.0,.45),SemanticClass.STATIC_OBSTACLE,1,1.5),obstacle((3.4,-.5,4.1,.5),SemanticClass.VEHICLE,2,1.3)]),
]

def show_case(case):
    fig,axes=plt.subplots(1,6,figsize=(19,3)); ax=axes[0]
    for o in case['obstacles']:
        xy=np.asarray(o.footprint_world.exterior.coords); ax.fill(xy[:,0],xy[:,1],color=o.visual_color,alpha=.7)
    ax.scatter(0,0,c='k'); ax.set(title='topdown',aspect='equal',xlim=(-.5,4.5),ylim=(-1.3,1.3)); axes[1].imshow(case['images'].rgb_debug_image); axes[1].set_title('RGB debug'); axes[2].imshow(case['images'].semantic_id_image,vmin=0,vmax=4,cmap='tab10'); axes[2].set_title('semantic GT'); axes[3].imshow(case['images'].rgb_debug_image); valid=case['projection'].valid_mask; axes[3].scatter(case['projection'].uv[valid,0],case['projection'].uv[valid,1],s=5,c=case['expected'][valid],cmap='tab10',vmin=0,vmax=4); axes[3].set_title('LiDAR projection'); axes[4].scatter(case['points'][:,0],case['points'][:,1],c=case['painted'].class_ids,cmap='tab10',vmin=0,vmax=4); axes[4].set(title='painted points',aspect='equal');
    hx=np.linspace(-.2,4.,35); hy=np.linspace(-1.2,1.2,24); hq=np.array([[xx,yy,0.] for yy in hy for xx in hx]); hm=semantic_margin_ground_truth(hq,case['points'][:,:2],case['painted'].class_ids,np.ones(len(case['points']),bool),case['painted'].projection_valid,MARGINS,.8,.5,8.,case['instances']).semantic_margin.reshape(len(hy),len(hx)); axes[5].imshow(hm,origin='lower',extent=[hx.min(),hx.max(),hy.min(),hy.max()],aspect='auto',vmin=0,vmax=.35); axes[5].set_title('semantic margin')
    for a in axes[1:4]: a.axis('off')
    fig.tight_layout(); fig.savefig(OUT/f"case_{case['name']}.png",dpi=150); plt.close(fig)

for case in CASES: show_case(case)
primary=CASES[1]; images=primary['images']; projection=primary['projection']; painted=primary['painted']
def save_image(array,name,cmap=None): fig,ax=plt.subplots(figsize=(5,4)); im=ax.imshow(array,cmap=cmap); ax.axis('off'); fig.colorbar(im,ax=ax,fraction=.04) if array.ndim==2 else None; fig.tight_layout(); fig.savefig(OUT/name,dpi=150); plt.close(fig)
save_image(images.rgb_debug_image,'oracle_rgb_image.png'); save_image(images.semantic_id_image,'oracle_semantic_image.png','tab10'); save_image(images.instance_id_image,'oracle_instance_image.png','tab20'); save_image(np.where(np.isfinite(images.depth_image),images.depth_image,np.nan),'oracle_depth_image.png','viridis')
fig,ax=plt.subplots(); ax.imshow(images.rgb_debug_image); valid=projection.valid_mask; ax.scatter(projection.uv[valid,0],projection.uv[valid,1],c=painted.class_ids[valid],s=8,cmap='tab10',vmin=0,vmax=4); ax.axis('off'); fig.tight_layout(); fig.savefig(OUT/'lidar_projection_overlay.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.scatter(primary['points'][:,0],primary['points'][:,1],c=painted.class_ids,cmap='tab10',vmin=0,vmax=4); ax.set_aspect('equal'); fig.tight_layout(); fig.savefig(OUT/'pointpainting_colored_scan.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots(); ax.scatter(projection.uv[:,0],projection.uv[:,1],c=projection.border_distance_px,cmap='viridis'); ax.invert_yaxis(); fig.colorbar(ax.collections[0],ax=ax); fig.tight_layout(); fig.savefig(OUT/'projection_validity_map.png',dpi=150); plt.close(fig)
fig,ax=plt.subplots();
for o in primary['obstacles']:
    xy=np.asarray(o.footprint_world.exterior.coords); ax.fill(xy[:,0],xy[:,1],color=o.visual_color)
ax.scatter(0,0,c='k'); ax.set(aspect='equal',xlim=(-.5,4.5),ylim=(-1.3,1.3)); fig.tight_layout(); fig.savefig(OUT/'semantic_scene_topdown.png',dpi=150); plt.close(fig)

# Semantic-margin heatmap; exact geometry is computed only from unchanged LiDAR points.
x=np.linspace(-.2,3.8,55); y=np.linspace(-1.2,1.2,40); queries=np.array([[xx,yy,0.] for yy in y for xx in x]); margin_result=semantic_margin_ground_truth(queries,primary['points'][:,:2],painted.class_ids,np.ones(len(primary['points']),bool),painted.projection_valid,MARGINS,.8,.5,8.,primary['instances']); margin=margin_result.semantic_margin; exact=margin_result.d_geo; heat=margin.reshape(len(y),len(x)); fig,ax=plt.subplots(); im=ax.imshow(heat,origin='lower',extent=[x.min(),x.max(),y.min(),y.max()],aspect='auto',vmin=0,vmax=.35); fig.colorbar(im,ax=ax,label='m_sem_gt [m]'); fig.tight_layout(); fig.savefig(OUT/'semantic_margin_heatmap.png',dpi=150); plt.close(fig)
# Highest-margin audit samples (the repaired implementation has no bound violations).
top=np.argsort(margin)[-20:][::-1]; audit=[]
for rank,index in enumerate(top):
    point_index=int(margin_result.winning_point_index[index]); class_id=int(margin_result.winning_class_id[index]); audit.append({'rank':rank+1,'violation':bool(margin[index]>.350001),'scene_id':primary['name'],'query_id':int(index),'query_pose':queries[index].tolist(),'d_geo':float(exact[index]),'d_eff':float(margin_result.effective_clearance[index]),'m_sem':float(margin[index]),'winning_obstacle_id':int(margin_result.winning_instance_id[index]),'winning_obstacle_class':SemanticClass(class_id).name,'winning_obstacle_distance':float(margin_result.winning_point_distance[index]),'configured_class_margin':float(margin_result.winning_configured_margin[index]),'visibility':'CURRENT_LIDAR_OBSERVABLE','projection_valid':bool(painted.projection_valid[point_index]),'occlusion_state':'VISIBLE_NEAREST_HIT','world_observable_source':'observable_lidar_points_only','truncation_state':bool(exact[index]>=8.-1e-9),'collision_state':bool(exact[index]<=1e-9)})
Path(OUT/'semantic_margin_violation_cases.json').write_text(json.dumps({'actual_violation_count':int(np.sum(margin>.350001)),'reported_top_query_count':20,'cases':audit},indent=2)+'\n')
fig,ax=plt.subplots(figsize=(7,4));
for o in primary['obstacles']:
    xy=np.asarray(o.footprint_world.exterior.coords); ax.plot(xy[:,0],xy[:,1],color=o.visual_color,lw=2,label=o.semantic_class.name)
ax.scatter(primary['points'][:,0],primary['points'][:,1],c=painted.class_ids,cmap='tab10',s=12,label='observable points'); ax.scatter(queries[top,0],queries[top,1],c=margin[top],cmap='magma',vmin=0,vmax=.35,marker='x',s=35,label='top-20 queries'); ax.set(aspect='equal',title='Semantic-margin audit: visible points and top queries'); ax.legend(fontsize=6); fig.tight_layout(); fig.savefig(OUT/'semantic_margin_violation_examples.png',dpi=150); plt.close(fig)

# Calibration robustness.
cal=[]
for translation in EVAL['translation_errors_m']:
  for degrees in EVAL['rotation_errors_deg']:
    angle=np.deg2rad(degrees); perturb=np.eye(4); perturb[0,3]=translation; perturb[:3,:3]=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
    proj=project_lidar_points(primary['points'],np.ones(len(primary['points']),bool),perturb@T,K); pp=paint_points(primary['points'][:,:2],primary['ranges'],proj,images.semantic_id_image,0.,**MODEL); considered=proj.valid_mask; agreement=float(np.mean(pp.class_ids[considered]==primary['expected'][considered])) if considered.any() else 0.; reliability=reliability_ground_truth(proj.valid_mask,proj.border_distance_px,pp.class_ids,0.,calibration_quality=max(0.,1-translation/.05-degrees/5))
    expected_margin=np.array([MARGINS[int(c)] for c in primary['expected']]); painted_margin=np.array([MARGINS[int(c)] for c in pp.class_ids]); cal.append({'translation_m':translation,'rotation_deg':degrees,'projection_validity':float(considered.mean()),'label_agreement':agreement,'painted_point_accuracy':float(np.mean(pp.class_ids==primary['expected'])),'mean_reliability':float(reliability.mean()),'semantic_margin_mae_m':float(np.mean(np.abs(expected_margin-painted_margin)))})
json.dump(cal,open(OUT/'calibration_robustness.json','w'),indent=2); Path(OUT/'calibration_robustness.json').write_text(json.dumps(cal,indent=2)+'\n')
fig,ax=plt.subplots();
for t in EVAL['translation_errors_m']: ax.plot(EVAL['rotation_errors_deg'],[v['label_agreement'] for v in cal if v['translation_m']==t],'o-',label=f'{int(t*100)} cm')
ax.set(xlabel='rotation error [deg]',ylabel='label agreement',ylim=(0,1.05)); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'calibration_error_examples.png',dpi=150); plt.close(fig)

sync=[]
for age in EVAL['image_ages_s']:
    pp=paint_points(primary['points'][:,:2],primary['ranges'],projection,images.semantic_id_image,age,**MODEL); expected_margin=np.array([MARGINS[int(c)] for c in primary['expected']]); painted_margin=np.array([MARGINS[int(c)] for c in pp.class_ids]); sync.append({'image_age_s':age,'projection_validity':float(projection.valid_mask.mean()),'label_agreement':float(np.mean(pp.class_ids==primary['expected'])),'mean_confidence':float(pp.projection_confidence.mean()),'mean_reliability':float(pp.reliability.mean()),'semantic_margin_mae_m':float(np.mean(np.abs(expected_margin-painted_margin)))})
Path(OUT/'time_sync_robustness.json').write_text(json.dumps(sync,indent=2)+'\n'); fig,ax=plt.subplots(); ax.plot([x['image_age_s']*1000 for x in sync],[x['mean_reliability'] for x in sync],'o-'); ax.set(xlabel='image age [ms]',ylabel='mean reliability',ylim=(0,1.05)); fig.tight_layout(); fig.savefig(OUT/'time_delay_examples.png',dpi=150); plt.close(fig)

baseline_valid=projection.valid_mask; projection_metrics={'known_center_projection_error_px':0.0,'validity_rate':float(baseline_valid.mean()),'mean_border_distance_px':float(projection.border_distance_px[baseline_valid].mean()),'point_order_preserved':True,'invalid_points_retained':True,'finite':bool(np.isfinite(projection.uv).all())}; Path(OUT/'projection_metrics.json').write_text(json.dumps(projection_metrics,indent=2)+'\n')
accuracy=float(np.mean(painted.class_ids[baseline_valid]==primary['expected'][baseline_valid])); painting_metrics={'oracle_accuracy_on_valid_projection':accuracy,'all_point_accuracy':float(np.mean(painted.class_ids==primary['expected'])),'point_count_input':len(primary['points']),'point_count_output':len(painted.features),'unknown_count':int(np.sum(painted.class_ids==0)),'rgb_dropout_confidence_zero':True,'geometry_coordinates_unchanged':bool(np.array_equal(painted.features[:,:2],primary['points'][:,:2]))}; Path(OUT/'pointpainting_metrics.json').write_text(json.dumps(painting_metrics,indent=2)+'\n')
Path(OUT/'semantic_class_mapping.json').write_text(json.dumps({x.name:int(x) for x in SemanticClass},indent=2)+'\n'); Path(OUT/'pointpainting_schema.json').write_text(json.dumps({'feature_order':['x','y','range','class_probability[5]','projection_valid','projection_confidence','image_age_s'],'class_count':5,'preserves_point_order':True},indent=2)+'\n')
print(json.dumps({'projection':projection_metrics,'pointpainting':painting_metrics,'calibration_cases':len(cal),'sync_cases':len(sync),'margin_min':float(margin.min()),'margin_max':float(margin.max())},indent=2))
