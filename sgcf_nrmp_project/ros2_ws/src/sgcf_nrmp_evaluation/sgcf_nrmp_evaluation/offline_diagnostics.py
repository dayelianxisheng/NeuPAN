from __future__ import annotations
import json
import rclpy
from rclpy.node import Node
from diagnostic_msgs.msg import DiagnosticArray,DiagnosticStatus,KeyValue
from std_msgs.msg import String

class Diagnostics(Node):
    def __init__(self):
        super().__init__('sgcf_nrmp_offline_diagnostics');self.pub=self.create_publisher(DiagnosticArray,'/diagnostics',10);self.create_subscription(String,'/sgcf/planner_diagnostics',self.cb,10)
    def cb(self,msg):
        d=json.loads(msg.data); a=DiagnosticArray();s=DiagnosticStatus();s.name='sgcf_nrmp/offline_planner';s.level=DiagnosticStatus.OK;s.message=d['result']['status'];s.values=[KeyValue(key='scene',value=d['scene']),KeyValue(key='mode',value=d['mode']),KeyValue(key='actuation_eligible',value=str(d['actuation_eligible']).lower()),KeyValue(key='offline_only',value='true')];a.status=[s];self.pub.publish(a)
def main():
    rclpy.init();n=Diagnostics()
    try:rclpy.spin(n)
    finally:n.destroy_node();rclpy.shutdown()

if __name__ == '__main__':
    main()
