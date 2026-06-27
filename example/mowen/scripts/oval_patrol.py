#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
椭圆路径巡逻 — 小车沿椭圆形路线持续行走
用法:
    python3 oval_patrol.py              # 默认椭圆巡逻
    python3 oval_patrol.py --stop       # 停止
    python3 oval_patrol.py --circle     # 圆形（短轴=长轴）

参数（可选）:
    --major 1.0   长轴半径 (m), 默认 1.0
    --minor 0.5   短轴半径 (m), 默认 0.5
    --speed 0.2   行进速度 (m/s), 默认 0.2
    --time 30     运行时间 (s), 默认 30
"""

import rospy, sys, math
from geometry_msgs.msg import Twist

RATE = 50  # Hz


def make_oval(major=1.0, minor=0.5, speed=0.2):
    """
    椭圆路径：根据当前角度返回 (vx, vy, wz)
    用参数方程: x = major*cos(t), y = minor*sin(t)
    速度方向沿椭圆切线，大小保持 speed
    """
    t = (rospy.Time.now().to_sec() * speed / (major + minor)) % (2 * math.pi)

    # 椭圆上的位置
    x = major * math.cos(t)
    y = minor * math.sin(t)

    # 切线方向 (dx/dt, dy/dt)
    dx = -major * math.sin(t)
    dy = minor * math.cos(t)

    # 归一化 → 单位方向向量
    norm = math.hypot(dx, dy)
    if norm < 1e-6:
        return 0.0, 0.0, 0.0

    # omni: vx, vy 是速度向量
    vx = speed * dx / norm
    vy = speed * dy / norm

    # 朝向角 (车头始终朝速度方向)
    # 当前角度 = arctan2(dy, dx)，上一帧角度差值 = 角速度
    return vx, vy, 0.0


if __name__ == '__main__':
    rospy.init_node('oval_patrol', anonymous=True)
    pub = rospy.Publisher('/cmd_vel', Twist, queue_size=5)
    rate = rospy.Rate(RATE)

    # 解析参数
    major = 1.0
    minor = 0.5
    speed = 0.2
    run_time = 30.0

    args = sys.argv[1:]
    if '--stop' in args or '-s' in args:
        # 发零速 3 秒
        rospy.loginfo("停止中...")
        t0 = rospy.Time.now()
        while (rospy.Time.now() - t0).to_sec() < 3.0:
            pub.publish(Twist())
            rate.sleep()
        sys.exit(0)

    # 可选参数
    arg_map = {'--major': 'major', '--minor': 'minor',
               '--speed': 'speed', '--time': 'run_time'}
    for i, a in enumerate(args):
        if a in arg_map:
            locals()[arg_map[a]] = float(args[i+1]) if i+1 < len(args) else 0.0

    if '--circle' in args or '-c' in args:
        major = minor = max(major, minor)

    rospy.loginfo(f"椭圆巡逻: 长轴={major}m 短轴={minor}m 速度={speed}m/s 时长={run_time}s")

    t_start = rospy.Time.now()
    while (rospy.Time.now() - t_start).to_sec() < run_time and not rospy.is_shutdown():
        vx, vy, wz = make_oval(major, minor, speed)
        twist = Twist()
        twist.linear.x = vx
        twist.linear.y = vy
        twist.angular.z = wz
        pub.publish(twist)
        rate.sleep()

    # 停止：持续零速 3 秒
    rospy.loginfo("巡逻结束，停止中...")
    t_stop = rospy.Time.now()
    while (rospy.Time.now() - t_stop).to_sec() < 3.0 and not rospy.is_shutdown():
        pub.publish(Twist())
        rate.sleep()
    pub.publish(Twist())
    rospy.loginfo("已停止")
