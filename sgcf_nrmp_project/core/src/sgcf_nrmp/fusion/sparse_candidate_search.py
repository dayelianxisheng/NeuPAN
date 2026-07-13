"""Deterministic, GT-free sparse semantic candidate generation on CPU."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class CandidateBatch:
    probabilities: np.ndarray
    uv: np.ndarray
    offsets: np.ndarray
    valid_mask: np.ndarray
    reliable_mask: np.ndarray


def sparse_grid_offsets(radius:int)->np.ndarray:
    definitions={8:[-8,-4,0,4,8],16:[-16,-8,0,8,16],24:[-24,-16,-8,0,8,16,24]}
    if radius not in definitions: raise ValueError("radius must be 8, 16, or 24")
    values=np.asarray(definitions[radius],int); return np.asarray([(x,y) for y in values for x in values],int)


def cross_offsets(radius:int)->np.ndarray:
    values=np.linspace(-radius,radius,7 if radius==24 else 5,dtype=int); return np.unique(np.vstack((np.c_[values,np.zeros(len(values),int)],np.c_[np.zeros(len(values),int),values])),axis=0)


def ring_offsets(radius:int,count:int=16)->np.ndarray:
    angles=np.linspace(0,2*np.pi,count,endpoint=False); offsets=np.rint(np.c_[np.cos(angles),np.sin(angles)]*radius).astype(int); return np.unique(np.vstack(([[0,0]],offsets)),axis=0)


def fixed_random_offsets(radius:int,count:int=32,seed:int=20260713)->np.ndarray:
    rng=np.random.default_rng(seed); values=rng.integers(-radius,radius+1,(count-1,2)); return np.unique(np.vstack(([[0,0]],values)),axis=0)[:count]


def pattern_offsets(name:str)->np.ndarray:
    if name=='C0_HARD_SINGLE_PIXEL': return np.asarray([[0,0]])
    if name=='C1_LOCAL_3X3': return np.asarray([(x,y) for y in (-1,0,1) for x in (-1,0,1)])
    if name=='C2_LOCAL_5X5': return np.asarray([(x,y) for y in range(-2,3) for x in range(-2,3)])
    if name=='C3_SPARSE_GRID_RADIUS_8': return sparse_grid_offsets(8)
    if name=='C4_SPARSE_GRID_RADIUS_16': return sparse_grid_offsets(16)
    if name=='C5_SPARSE_GRID_RADIUS_24': return sparse_grid_offsets(24)
    if name=='C7_MULTISCALE_PYRAMID_SEARCH':
        groups=[np.asarray([(x,y) for y in (-r,0,r) for x in (-r,0,r)]) for r in (2,8,16,24)]; return np.unique(np.vstack(groups),axis=0)
    raise ValueError(name)


def sample_candidates(probability_map,projected_uv,offsets,projection_valid,rgb_available=True,image_age_s=0.,max_image_age_s=.1)->CandidateBatch:
    probs=np.asarray(probability_map,float); uv=np.asarray(projected_uv,float); offsets=np.asarray(offsets,int); projection=np.asarray(projection_valid,bool)
    if probs.ndim!=3 or uv.ndim!=2 or uv.shape[1]!=2 or len(projection)!=len(uv) or offsets.ndim!=2 or offsets.shape[1]!=2: raise ValueError("invalid candidate input shape")
    center=np.rint(uv).astype(int); candidates=center[:,None,:]+offsets[None,:,:]; h,w,_=probs.shape; inside=(candidates[...,0]>=0)&(candidates[...,0]<w)&(candidates[...,1]>=0)&(candidates[...,1]<h)&projection[:,None]&bool(rgb_available)&(image_age_s<=max_image_age_s)
    clipped=candidates.copy(); clipped[...,0]=np.clip(clipped[...,0],0,w-1); clipped[...,1]=np.clip(clipped[...,1],0,h-1); sampled=probs[clipped[...,1],clipped[...,0]]; sampled=np.where(inside[...,None],sampled,0.); reliable=inside&(sampled[...,1:].sum(-1)>0)
    return CandidateBatch(sampled,clipped,offsets,inside,reliable)


def coarse_to_fine_candidates(probability_map,projected_uv,projection_valid,top_k=4,rgb_available=True,image_age_s=0.,max_image_age_s=.1)->CandidateBatch:
    coarse=sample_candidates(probability_map,projected_uv,sparse_grid_offsets(24),projection_valid,rgb_available,image_age_s,max_image_age_s); score=coarse.probabilities[...,1:].max(-1); score=np.where(coarse.valid_mask,score,-np.inf); top=np.argsort(score,axis=1)[:,-top_k:]; centers=np.take_along_axis(coarse.uv,top[...,None],axis=1); refine=np.asarray([(x,y) for y in (-1,0,1) for x in (-1,0,1)]); uv=(centers[:,:,None,:]+refine[None,None,:,:]).reshape(len(projected_uv),top_k*9,2); h,w,_=np.asarray(probability_map).shape; inside=(uv[...,0]>=0)&(uv[...,0]<w)&(uv[...,1]>=0)&(uv[...,1]<h)&np.asarray(projection_valid,bool)[:,None]&bool(rgb_available)&(image_age_s<=max_image_age_s); clipped=uv.copy(); clipped[...,0]=np.clip(clipped[...,0],0,w-1); clipped[...,1]=np.clip(clipped[...,1],0,h-1); probs=np.asarray(probability_map)[clipped[...,1],clipped[...,0]]; probs=np.where(inside[...,None],probs,0.); offsets=clipped-np.rint(projected_uv).astype(int)[:,None,:]; return CandidateBatch(probs,clipped,offsets,inside,inside&(probs[...,1:].sum(-1)>0))
