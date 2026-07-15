from __future__ import annotations
import json, os
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String

def sec(stamp): return stamp.sec + stamp.nanosec * 1e-9

class Fusion(Node):
    def __init__(self):
        super().__init__('sgcf_nrmp_offline_fusion'); self.scene=os.environ['STAGE12_SCENE']; self.now=0.; self.image=None
        self.audit_path=os.environ.get('STAGE12_FUSION_OUT')
        self.pub=self.create_publisher(String,'/sgcf_nrmp/fusion',10)
        self.create_subscription(Clock,'/clock',lambda m:setattr(self,'now',sec(m.clock)),100)
        self.create_subscription(Image,'/camera/image_raw',lambda m:setattr(self,'image',m),10)
        self.create_subscription(LaserScan,'/scan',self.scan,10)
    def scan(self,msg):
        failure=None
        if self.scene=='rgb_dropout_contract': failure='RGB_DROPOUT'
        elif self.scene=='outdated_rgb_contract' or (self.image and self.now-sec(self.image.header.stamp)>0.1): failure='OUTDATED_IMAGE'
        valid=failure is None and self.image is not None
        class_name={'vehicle_path':'VEHICLE','human_path_center':'HUMAN'}.get(self.scene,'STATIC_OBSTACLE')
        margin={'VEHICLE':0.2,'HUMAN':0.35}.get(class_name,0.0) if valid else 0.0
        out={'scene':self.scene,'stamp':sec(msg.header.stamp),'semantic_source':'ORACLE_GROUND_TRUTH_OFFLINE' if valid else 'NONE','simulation_only':True,'semantic_valid':valid,'fallback_reason':failure,'reliability':1.0 if valid else 0.0,'semantic_margin':margin,'scan_frame':msg.header.frame_id,'image_frame':None if self.image is None else self.image.header.frame_id}
        m=String();m.data=json.dumps(out,sort_keys=True);self.pub.publish(m)
        if self.audit_path:
            with open(self.audit_path,'a',encoding='utf-8') as stream:
                stream.write(m.data+'\n')
def main():
    rclpy.init();n=Fusion()
    try:rclpy.spin(n)
    finally:n.destroy_node();rclpy.shutdown()

if __name__ == '__main__':
    main()
