from __future__ import annotations
import json, math, os, time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from builtin_interfaces.msg import Time
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan,Image,CameraInfo
from nav_msgs.msg import Odometry
from tf2_msgs.msg import TFMessage
from geometry_msgs.msg import TransformStamped
from std_msgs.msg import String

def time_msg(v):
    m=Time();m.sec=int(v);m.nanosec=int(round((v-int(v))*1e9));return m

class Publisher(Node):
    def __init__(self):
        super().__init__('sgcf_nrmp_synthetic_sensor_publisher');self.scene=os.environ['STAGE12_SCENE'];p=Path(os.environ['STAGE12_SNAPSHOT_DIR']);self.samples=[json.loads(x.read_text()) for x in sorted(p.glob('sample_*.json'))];assert self.samples
        self.i=0;self.base=10.0;self.done=False
        self.clock=self.create_publisher(Clock,'/clock',100);self.scan=self.create_publisher(LaserScan,'/scan',10);self.image=self.create_publisher(Image,'/camera/image_raw',10);self.info=self.create_publisher(CameraInfo,'/camera/camera_info',10);self.odom=self.create_publisher(Odometry,'/odom',10);self.tf=self.create_publisher(TFMessage,'/tf',10)
        qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL);self.tf_static=self.create_publisher(TFMessage,'/tf_static',qos);self.context_pub=self.create_publisher(String,'/sgcf_nrmp/offline_scene',10);self.end=self.create_publisher(String,'/stage12/end',10)
        self.publish_static();self.timer=self.create_timer(.35,self.tick)
    def publish_static(self):
        transforms=[]
        for child,x,y,z in [('sgcf_robot/lidar_link/lidar',0.,0.,.35),('sgcf_robot/camera_link/rgb_camera',.1,0.,.4)]:
            t=TransformStamped();t.header.frame_id='base_link';t.child_frame_id=child;t.transform.translation.x=x;t.transform.translation.y=y;t.transform.translation.z=z;t.transform.rotation.w=1.;transforms.append(t)
        self.tf_static.publish(TFMessage(transforms=transforms))
    def tick(self):
        sim=self.base+self.i*.05
        for k in range(5): c=Clock();c.clock=time_msg(sim+k*.001);self.clock.publish(c)
        frame_index=self.i-10
        if 0 <= frame_index < 30:
            d=self.samples[frame_index%len(self.samples)];stamp=time_msg(sim); laser=d['laser']
            s=LaserScan();s.header.stamp=stamp;s.header.frame_id=laser['frame_id'];s.angle_min=float(laser['angle_min']);s.angle_increment=float(laser['angle_increment']);s.angle_max=s.angle_min+s.angle_increment*(len(laser['ranges'])-1);s.range_min=float(laser['range_min']);s.range_max=float(laser['range_max']);s.ranges=[math.inf if x is None else float(x) for x in laser['ranges']]
            o=Odometry();o.header.stamp=stamp;o.header.frame_id='odom';o.child_frame_id='base_link';o.pose.pose.position.x=float(d['robot_pose'][0]);o.pose.pose.position.y=float(d['robot_pose'][1]);yaw=float(d['robot_pose'][2]);o.pose.pose.orientation.z=math.sin(yaw/2);o.pose.pose.orientation.w=math.cos(yaw/2);o.twist.twist.linear.x=float(d['robot_velocity'][0]);o.twist.twist.angular.z=float(d['robot_velocity'][1]);self.odom.publish(o)
            info=d['camera_info'];ci=CameraInfo();ci.header.stamp=stamp;ci.header.frame_id=info['frame_id'];ci.width=info['width'];ci.height=info['height'];ci.k=info['k'];ci.p=[info['k'][0],0.,info['k'][2],0.,0.,info['k'][4],info['k'][5],0.,0.,0.,1.,0.];self.info.publish(ci)
            if self.scene!='rgb_dropout_contract':
                im=Image();image_stamp=sim-.100001 if self.scene=='outdated_rgb_contract' else sim;im.header.stamp=time_msg(image_stamp);im.header.frame_id=info['frame_id'];im.width=info['width'];im.height=info['height'];im.encoding='rgb8';im.step=im.width*3;value=sum(self.scene.encode())%251;im.data=bytes([value])*(im.step*im.height);self.image.publish(im)
            dynamic=TransformStamped();dynamic.header.stamp=stamp;dynamic.header.frame_id='odom';dynamic.child_frame_id='base_link';dynamic.transform.translation.x=o.pose.pose.position.x;dynamic.transform.translation.y=o.pose.pose.position.y;dynamic.transform.rotation=o.pose.pose.orientation;self.tf.publish(TFMessage(transforms=[dynamic]))
            c=String();c.data=json.dumps({'scene':self.scene,'source':'STAGE11C_SNAPSHOT','simulation_time':sim},sort_keys=True);self.context_pub.publish(c)
            # Publish the scan after its synchronized state, image, intrinsics,
            # and transform have entered DDS. Message stamps remain simulated.
            time.sleep(.01);self.scan.publish(s)
        elif self.i>=48:
            e=String();e.data='END';self.end.publish(e);self.done=True;self.timer.cancel()
        self.i+=1
def main():
    rclpy.init();n=Publisher()
    try:
        while rclpy.ok() and not n.done:rclpy.spin_once(n,timeout_sec=.1)
    finally:n.destroy_node();rclpy.shutdown()

if __name__ == '__main__':
    main()
