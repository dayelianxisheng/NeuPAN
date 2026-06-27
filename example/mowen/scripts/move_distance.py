#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Move a fixed distance / rotate a fixed angle.
Publishes at 50Hz during the whole movement.

Usage:
    python3 move_distance.py forward 0.5
    python3 move_distance.py left 0.3
    python3 move_distance.py rotate_left 90
    python3 move_distance.py stop

Notes:
    - MCU 的×1000缩放系数对应实际速度约×0.47, 脚本内部用 SPEED_CALIB 补偿
    - 如果速度不准, 调整 SPEED_CALIB 值: 实际距离=命令距离×SPEED_CALIB
    - 小车必须先切到串口模式（遥控器操作), 否则会卡顿
"""

import rospy
import sys
import math
from geometry_msgs.msg import Twist

RATE = 50           # Hz, 实测<20Hz会导致卡顿
DEFAULT_SPEED = 0.4  # m/s 命令速度 (实际约 0.19 m/s)
DEFAULT_TURN = 0.8   # rad/s

# MCU 速度校准因子: 命令速度 × SPEED_CALIB ≈ 实际速度
# 小车实测: 0.8 m/s 4s → 约 1.5m, 校准 ≈ 0.47
# 调整此值使 move_distance 距离准确
SPEED_CALIB = 0.5


def move(linear_x=0.0, linear_y=0.0, angular_z=0.0, duration=0.0):
    pub = rospy.Publisher('/cmd_vel', Twist, queue_size=5)
    rospy.sleep(0.3)

    twist = Twist()
    twist.linear.x = linear_x
    twist.linear.y = linear_y
    twist.angular.z = angular_z

    rate = rospy.Rate(RATE)
    t0 = rospy.Time.now()

    rospy.loginfo("start v=(%.3f,%.3f,%.3f) dur=%.1fs" % (linear_x, linear_y, angular_z, duration))
    while (rospy.Time.now() - t0).to_sec() < duration and not rospy.is_shutdown():
        pub.publish(twist)
        rate.sleep()

    # stop — MCU 保持最后速度（Bug #11），须持续发零速覆盖
    rospy.loginfo("🛑 停止中 (发零速 2 秒)...")
    t_stop = rospy.Time.now()
    while (rospy.Time.now() - t_stop).to_sec() < 2.0 and not rospy.is_shutdown():
        pub.publish(Twist())
        rate.sleep()
    pub.publish(Twist())
    rospy.loginfo("🛑 已停止")


if __name__ == '__main__':
    rospy.init_node('move_distance', anonymous=True)

    if len(sys.argv) < 2 or sys.argv[1] == 'stop':
        # stop = 发零速 3 秒覆盖 MCU 缓存
        move(0.0, 0.0, 0.0, 3.0)
        sys.exit(0)

    cmd = sys.argv[1]
    val = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0

    table = {
        'forward': (DEFAULT_SPEED, 0.0, 0.0),
        'f': (DEFAULT_SPEED, 0.0, 0.0),
        'backward': (-DEFAULT_SPEED, 0.0, 0.0),
        'b': (-DEFAULT_SPEED, 0.0, 0.0),
        'left': (0.0, DEFAULT_SPEED, 0.0),
        'l': (0.0, DEFAULT_SPEED, 0.0),
        'right': (0.0, -DEFAULT_SPEED, 0.0),
        'r': (0.0, -DEFAULT_SPEED, 0.0),
        'rotate_left': (0.0, 0.0, DEFAULT_TURN),
        'rl': (0.0, 0.0, DEFAULT_TURN),
        'rotate_right': (0.0, 0.0, -DEFAULT_TURN),
        'rr': (0.0, 0.0, -DEFAULT_TURN),
    }

    if cmd in ('rotate_left', 'rl', 'rotate_right', 'rr'):
        rad = math.radians(val)
        dur = rad / DEFAULT_TURN
    elif cmd in table:
        # 补偿 MCU 速度偏差: 实际速度 = 命令速度 × SPEED_CALIB
        dur = val / (DEFAULT_SPEED * SPEED_CALIB)
    else:
        print("unknown cmd: %s" % cmd)
        sys.exit(1)

    lx, ly, az = table[cmd]
    move(lx, ly, az, dur)
