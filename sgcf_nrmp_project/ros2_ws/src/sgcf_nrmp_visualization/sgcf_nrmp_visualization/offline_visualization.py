from __future__ import annotations
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped
from visualization_msgs.msg import Marker, MarkerArray

class Visualization(Node):
    def __init__(self):
        super().__init__('sgcf_nrmp_offline_visualization');self.path_pub=self.create_publisher(Path,'/sgcf_nrmp/local_plan',10);self.marker_pub=self.create_publisher(MarkerArray,'/sgcf_nrmp/markers',10);self.create_subscription(String,'/sgcf/planner_diagnostics',self.cb,10)
    def cb(self,msg):
        d=json.loads(msg.data); states=d.get('geometry_diagnosis',{}).get('nominal_states_samples',[]); states=states[-1] if states else [d.get('robot_pose',[0,0,0])]
        p=Path();p.header.frame_id='odom'
        for i,s in enumerate(states): q=PoseStamped();q.header.frame_id='odom';q.header.stamp.sec=int(d['simulation_timestamp']);q.header.stamp.nanosec=int((d['simulation_timestamp']%1)*1e9);q.pose.position.x=float(s[0]);q.pose.position.y=float(s[1]);q.pose.orientation.w=1.;p.poses.append(q)
        self.path_pub.publish(p); marker=Marker();marker.header=p.header;marker.ns='sgcf_local_plan';marker.id=0;marker.type=Marker.LINE_STRIP;marker.action=Marker.ADD;marker.scale.x=.02;marker.color.g=1.;marker.color.a=1.;marker.points=[q.pose.position for q in p.poses];self.marker_pub.publish(MarkerArray(markers=[marker]))
def main():
    rclpy.init();n=Visualization()
    try:rclpy.spin(n)
    finally:n.destroy_node();rclpy.shutdown()

if __name__ == '__main__':
    main()
