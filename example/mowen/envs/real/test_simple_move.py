#!/usr/bin/env python3
"""
mowen 新小车 — 简化测试脚本
功能: 直线走 + 避障测试

使用方法:
    python3 test_simple_move.py

前提条件:
1. 小车端已启动 robot_minimal.launch
2. NeuPAN 节点已通过 test_simple_straight.launch 启动
"""
import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import String
import math
import sys


class SimpleMoveTest:
    def __init__(self):
        rospy.init_node('simple_move_test', anonymous=True)

        # Publisher
        self.goal_pub = rospy.Publisher('/move_base_simple/goal', PoseStamped, queue_size=1)

        # Subscriber
        self.odom = None
        rospy.Subscriber('/odom', Odometry, self.odom_cb)

        rospy.loginfo("[SimpleMoveTest] Waiting for odometry...")
        rospy.sleep(2)

        if self.odom is None:
            rospy.logerr("[SimpleMoveTest] No odometry received! Check if /odom topic exists.")
            sys.exit(1)

    def odom_cb(self, msg):
        self.odom = msg

    def get_current_pos(self):
        """获取当前位置"""
        if self.odom is None:
            return [0, 0]
        return [self.odom.pose.pose.position.x, self.odom.pose.pose.position.y]

    def send_goal(self, x, y, theta=0.0):
        """发送目标点"""
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.header.stamp = rospy.Time.now()
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.position.z = 0.0

        # 四元数（简化：只考虑 yaw）
        goal.pose.orientation.x = 0.0
        goal.pose.orientation.y = 0.0
        goal.pose.orientation.z = math.sin(theta / 2)
        goal.pose.orientation.w = math.cos(theta / 2)

        self.goal_pub.publish(goal)
        rospy.loginfo(f"[SimpleMoveTest] Goal sent: ({x:.2f}, {y:.2f}, {math.degrees(theta):.1f}°)")

    def wait_for_arrival(self, target_x, target_y, timeout=60, threshold=0.25):
        """等待到达目标点"""
        start_time = rospy.Time.now()
        rate = rospy.Rate(5)  # 5Hz

        rospy.loginfo(f"[SimpleMoveTest] Waiting for arrival (threshold={threshold}m, timeout={timeout}s)...")

        while not rospy.is_shutdown():
            current_x, current_y = self.get_current_pos()
            dist = math.sqrt((current_x - target_x)**2 + (current_y - target_y)**2)

            # 打印进度
            elapsed = (rospy.Time.now() - start_time).to_sec()
            rospy.loginfo_throttle(3, f"[SimpleMoveTest] Distance to goal: {dist:.2f}m (elapsed: {elapsed:.1f}s)")

            # 检查到达
            if dist < threshold:
                rospy.loginfo(f"[SimpleMoveTest] ✓ Arrived! Final distance: {dist:.2f}m")
                return True

            # 检查超时
            if elapsed > timeout:
                rospy.logwarn(f"[SimpleMoveTest] ✗ Timeout! Current distance: {dist:.2f}m")
                return False

            rate.sleep()

        return False


def main():
    try:
        tester = SimpleMoveTest()

        rospy.loginfo("=" * 60)
        rospy.loginfo(" mowen 新小车 — 简化测试")
        rospy.loginfo(" 测试内容: 直线前进 + 避障")
        rospy.loginfo("=" * 60)

        # 获取起点
        start_x, start_y = tester.get_current_pos()
        rospy.loginfo(f"[SimpleMoveTest] Start position: ({start_x:.2f}, {start_y:.2f})")

        # 测试序列
        rospy.loginfo("\n[Test 1/3] 前进 1 米")
        tester.send_goal(start_x + 1.0, start_y)
        if not tester.wait_for_arrival(start_x + 1.0, start_y, timeout=30):
            rospy.logerr("Test 1 failed!")
            return
        rospy.sleep(2)

        rospy.loginfo("\n[Test 2/3] 继续前进 1 米（测试避障）")
        rospy.loginfo("         提示: 可在路径上放置障碍物测试避障")
        tester.send_goal(start_x + 2.0, start_y)
        if not tester.wait_for_arrival(start_x + 2.0, start_y, timeout=40):
            rospy.logwarn("Test 2 timeout (可能遇到障碍物)")
        rospy.sleep(2)

        rospy.loginfo("\n[Test 3/3] 返回起点")
        tester.send_goal(start_x, start_y)
        if not tester.wait_for_arrival(start_x, start_y, timeout=40):
            rospy.logwarn("Test 3 timeout")

        rospy.loginfo("\n" + "=" * 60)
        rospy.loginfo(" 测试完成！")
        rospy.loginfo("=" * 60)

    except rospy.ROSInterruptException:
        rospy.loginfo("Test interrupted by user")
    except Exception as e:
        rospy.logerr(f"Test error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
