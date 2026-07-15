from __future__ import annotations
import hashlib,json,os,sqlite3,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from rclpy.serialization import serialize_message,deserialize_message
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan,Image,CameraInfo
from nav_msgs.msg import Odometry,Path as NavPath
from tf2_msgs.msg import TFMessage
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from visualization_msgs.msg import MarkerArray
from diagnostic_msgs.msg import DiagnosticArray
from rosidl_runtime_py.convert import message_to_ordereddict

TYPES={'/clock':Clock,'/scan':LaserScan,'/camera/image_raw':Image,'/camera/camera_info':CameraInfo,'/odom':Odometry,'/tf':TFMessage,'/tf_static':TFMessage,'/sgcf_nrmp/fusion':String,'/sgcf/planner_candidate_cmd_vel':Twist,'/sgcf/planner_status':String,'/sgcf/planner_diagnostics':String,'/sgcf_nrmp/local_plan':NavPath,'/sgcf_nrmp/markers':MarkerArray,'/diagnostics':DiagnosticArray}
TYPE_NAMES={k:v.__module__.split('.')[0]+'/msg/'+v.__name__ for k,v in TYPES.items()}

class Recorder(Node):
    def __init__(self,path):
        super().__init__('sgcf_nrmp_offline_bag_recorder');self.path=path;self.rows=[];self.done=False
        for topic,cls in TYPES.items(): self.create_subscription(cls,topic,lambda m,t=topic:self.cb(t,m),QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL) if topic=='/tf_static' else 100)
        self.create_subscription(String,'/stage12/end',self.stop,10)
    def cb(self,topic,msg): self.rows.append((len(self.rows),topic,TYPE_NAMES[topic],time.monotonic_ns(),bytes(serialize_message(msg))))
    def stop(self,_): self.done=True
    def save(self):
        if self.path.exists(): self.path.unlink()
        db=sqlite3.connect(self.path);db.execute('create table messages(seq integer primary key,topic text,type text,receive_ns integer,payload blob)');db.executemany('insert into messages values(?,?,?,?,?)',self.rows);db.commit();db.close()
        counts={t:sum(r[1]==t for r in self.rows) for t in TYPES};(self.path.with_suffix('.metadata.json')).write_text(json.dumps({'format':'SGCF_SELF_CONTAINED_SQLITE_CDR_V1','message_count':len(self.rows),'topics':TYPE_NAMES,'counts':counts},indent=2)+'\n')

class Replayer(Node):
    def __init__(self,path):
        super().__init__('sgcf_nrmp_offline_bag_replayer');self.rows=sqlite3.connect(path).execute('select topic,payload from messages order by seq').fetchall();self.i=0;self.done=False;self.ready=time.monotonic()+1.;self.drain_until=None;self.pubs={t:self.create_publisher(TYPES[t],t,QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL) if t=='/tf_static' else 100) for t in TYPES};self.timer=self.create_timer(.01,self.tick);self.end=self.create_publisher(String,'/stage12/replay_end',10)
    def tick(self):
        if time.monotonic()<self.ready:return
        if self.i>=len(self.rows):
            if self.drain_until is None:self.drain_until=time.monotonic()+1.;return
            if time.monotonic()<self.drain_until:return
            for _ in range(5):e=String();e.data='END';self.end.publish(e)
            self.done=True;self.timer.cancel();return
        t,p=self.rows[self.i];self.pubs[t].publish(deserialize_message(p,TYPES[t]));self.i+=1

class Auditor(Node):
    def __init__(self,out):
        super().__init__('sgcf_nrmp_offline_replay_auditor');self.out=out;self.hashes={t:[] for t in TYPES};self.done=False
        for topic,cls in TYPES.items():self.create_subscription(cls,topic,lambda m,t=topic:self.cb(t,m),QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL) if topic=='/tf_static' else 100)
        self.create_subscription(String,'/stage12/replay_end',lambda _:setattr(self,'done',True),10)
    def cb(self,t,m):
        # Hash the logical ROS message rather than raw CDR padding bytes.  CDR
        # alignment padding is not a message field and may be uninitialized.
        canonical=json.dumps(message_to_ordereddict(m),sort_keys=True,separators=(',',':'),allow_nan=True)
        self.hashes[t].append(hashlib.sha256(canonical.encode()).hexdigest())
    def save(self):self.out.write_text(json.dumps({'topics':self.hashes,'counts':{k:len(v) for k,v in self.hashes.items()}},sort_keys=True,indent=2)+'\n')

def spin_until(node,limit=120):
    end=time.monotonic()+limit
    while rclpy.ok() and not node.done:
        if time.monotonic()>end:raise TimeoutError(type(node).__name__)
        rclpy.spin_once(node,timeout_sec=.05)

def record_main():
    rclpy.init();n=Recorder(Path(os.environ['STAGE12_BAG_PATH']))
    try:spin_until(n);n.save()
    finally:n.destroy_node();rclpy.shutdown()
def replay_main():
    rclpy.init();n=Replayer(Path(os.environ['STAGE12_BAG_PATH']))
    try:spin_until(n)
    finally:n.destroy_node();rclpy.shutdown()
def audit_main():
    rclpy.init();n=Auditor(Path(os.environ['STAGE12_REPLAY_AUDIT']))
    try:spin_until(n);n.save()
    finally:n.destroy_node();rclpy.shutdown()
