#!/usr/bin/env python3.9
"""小车上点移动 + NeuPAN 避障"""
import rospy
from geometry_msgs.msg import Twist, PoseStamped
from nav_msgs.msg import Odometry, Path
import math, sys


class NeuPANMover:
    def __init__(self):
        self.goal_pub = rospy.Publisher('/move_base_simple/goal', PoseStamped, queue_size=1)
        self.path_pub = rospy.Publisher('/mover_path', Path, queue_size=1)
        self.odom = None
        self.trail = Path()
        self.trail.header.frame_id = 'odom'
        rospy.Subscriber('/odom', Odometry, self.odom_cb)
        rospy.sleep(1)

    def odom_cb(self, msg):
        self.odom = msg
        p = PoseStamped()
        p.header = msg.header
        p.pose = msg.pose.pose
        self.trail.poses.append(p)
        self.path_pub.publish(self.trail)

    def get_pos(self):
        if self.odom is None: return [0, 0]
        return [self.odom.pose.pose.position.x, self.odom.pose.pose.position.y]

    def goto(self, x, y, speed=0.15, timeout=60):
        """让 NeuPAN 导航到目标点，等待到达"""
        start = list(self.get_pos())
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.orientation.w = 1.0
        self.goal_pub.publish(goal)
        rospy.loginfo(f"[DOCKER] Goal sent: ({x:.1f}, {y:.1f})")

        t0 = rospy.Time.now()
        rate = rospy.Rate(5)
        while not rospy.is_shutdown():
            px, py = self.get_pos()
            dist = math.sqrt((px-x)**2 + (py-y)**2)
            if dist < 0.15:  # 15cm 容差
                rospy.loginfo(f"[DOCKER] Arrived! dist={dist:.2f}m")
                break
            if (rospy.Time.now() - t0).to_sec() > timeout:
                rospy.logwarn("[DOCKER] Timeout")
                break
            rate.sleep()


if __name__ == '__main__':
    rospy.init_node('neupan_mover', anonymous=True)
    m = NeuPANMover()

    # 默认巡逻路线
    points = [[1.0, 0.0], [0.0, 0.0], [-1.0, 0.0], [0.0, 0.0]]
    if len(sys.argv) > 1:
        args = [float(x) for x in sys.argv[1:]]
        points = [[args[i], args[i+1]] for i in range(0, len(args), 2)]

    rospy.loginfo(f"[DOCKER] Patrol: {points}")
    for x, y in points:
        if rospy.is_shutdown(): break
        m.goto(x, y)
        rospy.sleep(1)
    rospy.loginfo("[DOCKER] Done")
