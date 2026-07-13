"""Leakage-controlled synthetic RGB appearances for Stage 10."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from sgcf_nrmp.types.semantic import SemanticClass


@dataclass(frozen=True)
class AppearanceScene:
    image_rgb: np.ndarray
    semantic_mask: np.ndarray
    instance_mask: np.ndarray
    occluded_mask: np.ndarray


_PALETTE=((190,55,55),(55,105,190),(55,155,85),(190,145,45),(145,70,170),(70,165,170),(150,115,80))


def _draw_object(draw:ImageDraw.ImageDraw, mask:ImageDraw.ImageDraw, instance:ImageDraw.ImageDraw,
                 klass:SemanticClass, box, color, instance_id:int, rng):
    x0,y0,x1,y1=map(int,box); w=x1-x0; h=y1-y0
    def part(shape,coords,fill=color,**kwargs):
        getattr(draw,shape)(coords,fill=fill,**kwargs); getattr(mask,shape)(coords,fill=int(klass),**kwargs); getattr(instance,shape)(coords,fill=instance_id,**kwargs)
    dark=tuple(max(0,c-55) for c in color); light=tuple(min(255,c+45) for c in color)
    if klass==SemanticClass.STATIC_OBSTACLE:
        part('rectangle',(x0,y0,x1,y1));
        for xx in range(x0+4,x1,7): draw.line((xx,y0,xx,y1),fill=dark,width=1)
    elif klass==SemanticClass.HUMAN:
        head=(x0+w*.32,y0,x0+w*.68,y0+h*.25); part('ellipse',head,light)
        part('rounded_rectangle',(x0+w*.28,y0+h*.22,x0+w*.72,y0+h*.72),radius=max(2,int(w*.12)))
        part('polygon',[(x0+w*.3,y0+h*.65),(x0+w*.48,y0+h),(x0+w*.58,y0+h*.65),(x0+w*.75,y0+h)])
    elif klass==SemanticClass.VEHICLE:
        part('rounded_rectangle',(x0,y0+h*.28,x1,y0+h*.82),radius=max(2,int(h*.14)))
        part('polygon',[(x0+w*.22,y0+h*.28),(x0+w*.36,y0+h*.06),(x0+w*.72,y0+h*.06),(x0+w*.86,y0+h*.28)],light)
        for cx in (x0+w*.22,x0+w*.78): part('ellipse',(cx-w*.10,y0+h*.72,cx+w*.10,y1),dark)
    elif klass==SemanticClass.ROBOT:
        part('rounded_rectangle',(x0+w*.08,y0+h*.35,x0+w*.92,y1),radius=max(2,int(w*.1)))
        part('rectangle',(x0+w*.25,y0+h*.12,x0+w*.75,y0+h*.5),light)
        part('ellipse',(x0+w*.42,y0,x0+w*.58,y0+h*.16),dark)
        part('line',(x0+w*.5,y0+h*.12,x0+w*.5,y0),dark,width=max(1,int(w*.05)))
    # Class-independent texture: every texture can appear on every class.
    texture=int(rng.integers(0,3))
    canvas=draw._image; textured=canvas.copy(); texture_draw=ImageDraw.Draw(textured)
    if texture==1:
        for yy in range(y0+3,y1,6): texture_draw.line((x0,yy,x1,yy),fill=dark,width=1)
    elif texture==2:
        for _ in range(max(2,w*h//150)):
            xx=int(rng.integers(x0,max(x0+1,x1))); yy=int(rng.integers(y0,max(y0+1,y1))); texture_draw.ellipse((xx-1,yy-1,xx+1,yy+1),fill=light)
    if texture:
        current_instance=(np.asarray(instance._image)==instance_id).astype(np.uint8)*255
        canvas.paste(textured,mask=Image.fromarray(current_instance,'L'))


def render_appearance_scene(width:int,height:int,geometry_seed:int,appearance_seed:int,camera_seed:int)->AppearanceScene:
    """Render one reproducible scene; semantic/instance images are labels only."""
    geometry=np.random.default_rng(geometry_seed); appearance=np.random.default_rng(appearance_seed); camera=np.random.default_rng(camera_seed)
    bg=np.asarray(appearance.integers(35,205,size=3),dtype=np.uint8); image=Image.new('RGB',(width,height),tuple(bg)); draw=ImageDraw.Draw(image)
    # Background variation independent of object class.
    for _ in range(20):
        c=tuple(appearance.integers(20,235,size=3).tolist()); x=int(appearance.integers(0,width)); y=int(appearance.integers(0,height)); r=int(appearance.integers(2,10)); draw.ellipse((x-r,y-r,x+r,y+r),fill=c)
    semantic=Image.new('L',(width,height),0); instance=Image.new('I',(width,height),0); sm=ImageDraw.Draw(semantic); im=ImageDraw.Draw(instance)
    slots=[(4,8,width//4-3,height-8),(width//4+2,15,width//2-3,height-8),(width//2+2,10,3*width//4-3,height-8),(3*width//4+2,12,width-4,height-8)]
    classes=[SemanticClass.STATIC_OBSTACLE,SemanticClass.HUMAN,SemanticClass.VEHICLE,SemanticClass.ROBOT]; geometry.shuffle(classes)
    for idx,(klass,slot) in enumerate(zip(classes,slots),1):
        sx0,sy0,sx1,sy1=slot; scale=float(geometry.uniform(.68,.96)); sw=(sx1-sx0)*scale; sh=(sy1-sy0)*scale
        if klass==SemanticClass.HUMAN: sw*=.70
        if klass==SemanticClass.VEHICLE: sh*=.62
        if klass==SemanticClass.ROBOT: sh*=.78
        cx=(sx0+sx1)/2+geometry.uniform(-2,2); y1=sy1-geometry.uniform(0,3); box=(cx-sw/2,y1-sh,cx+sw/2,y1)
        color=_PALETTE[int(appearance.integers(0,len(_PALETTE)))]
        _draw_object(draw,sm,im,klass,box,color,idx,appearance)
    # Partial occlusion is visual and labeled UNKNOWN because content is not observable.
    occluded=Image.new('L',(width,height),0); od=ImageDraw.Draw(occluded)
    if appearance.random()<.65:
        ox=int(appearance.integers(width//6,5*width//6)); ow=int(appearance.integers(5,15)); od.rectangle((ox,0,ox+ow,height),fill=1); draw.rectangle((ox,0,ox+ow,height),fill=tuple(bg)); sm.rectangle((ox,0,ox+ow,height),fill=0); im.rectangle((ox,0,ox+ow,height),fill=0)
    image=ImageEnhance.Brightness(image).enhance(float(camera.uniform(.72,1.28))); image=ImageEnhance.Contrast(image).enhance(float(camera.uniform(.72,1.32)))
    if camera.random()<.65: image=image.filter(ImageFilter.GaussianBlur(radius=float(camera.uniform(0,.8))))
    rgb=np.asarray(image,dtype=np.float32); rgb+=camera.normal(0,float(camera.uniform(1,9)),rgb.shape); rgb=np.clip(rgb,0,255).astype(np.uint8)
    return AppearanceScene(rgb,np.asarray(semantic,dtype=np.uint8),np.asarray(instance,dtype=np.int32),np.asarray(occluded,dtype=bool))
