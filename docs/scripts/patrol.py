#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来回巡逻 — 前进 → 掉头 → 前进(返回) → 掉头 → 循环
从车的视角看永远是"往前走"。
用法:
    python3 patrol.py                  # 默认参数
    python3 patrol.py --stop           # 急停
    python3 patrol.py --dist 3.0       # 单程距离
    python3 patrol.py --speed 0.2      # 速度
    python3 patrol.py --lap 5          # 循环次数
"""

import rospy, sys, math
from geometry_msgs.msg import Twist

RATE = 50
DEFAULT_SPEED = 0.15
DEFAULT_DIST = 3.0
DEFAULT_LAPS = 3
TURN_SPEED = 0.4      # 掉头角速度 (rad/s)
TURN_CALIB = 0.5       # 实际转速 ≈ 命令 × 0.5 (调小=转更久) (MCU 偏差补偿)


def move_cmd(lx=0.0, ly=0.0, az=0.0, duration=0.0, pub=None, rate=None):
    twist = Twist()
    twist.linear.x = lx
    twist.linear.y = ly
    twist.angular.z = az
    t0 = rospy.Time.now()
    while (rospy.Time.now() - t0).to_sec() < duration and not rospy.is_shutdown():
        pub.publish(twist)
        rate.sleep()


def stop(pub=None, rate=None):
    t0 = rospy.Time.now()
    while (rospy.Time.now() - t0).to_sec() < 3.0 and not rospy.is_shutdown():
        pub.publish(Twist())
        rate.sleep()


if __name__ == '__main__':
    rospy.init_node('patrol', anonymous=True)
    pub = rospy.Publisher('/cmd_vel', Twist, queue_size=5)
    rate = rospy.Rate(RATE)

    dist = DEFAULT_DIST
    speed = DEFAULT_SPEED
    laps = DEFAULT_LAPS
    turn_sec = None  # 手动指定掉头秒数，None=自动计算
    args = sys.argv[1:]

    if '--stop' in args or '-s' in args:
        rospy.loginfo("急停...")
        stop(pub, rate)
        sys.exit(0)

    for i, a in enumerate(args):
        if a == '--dist' and i+1 < len(args): dist = float(args[i+1])
        elif a == '--speed' and i+1 < len(args): speed = float(args[i+1])
        elif a == '--lap' and i+1 < len(args): laps = int(args[i+1])
        elif a == '--turn-calib' and i+1 < len(args): TURN_CALIB = float(args[i+1])
        elif a == '--turn-sec' and i+1 < len(args): turn_sec = float(args[i+1])

    dur = dist / speed
    # 掉头 180°: 自动计算 或 手动指定
    if turn_sec is not None:
        turn_dur = turn_sec
    else:
        turn_dur = math.pi / (TURN_SPEED * TURN_CALIB)

    rospy.loginfo(f"巡逻: 距离={dist}m 速度={speed}m/s 共{laps}趟")
    rospy.loginfo(f"     掉头: {turn_dur:.1f}s = 180° @ {TURN_SPEED}rad/s × {TURN_CALIB}")
    rospy.loginfo("另开终端执行: python3 patrol.py --stop 急停")

    rospy.sleep(1)

    for lap in range(laps):
        rospy.loginfo(f"=== 第 {lap+1}/{laps} 趟 ===")

        # 前进(往)
        rospy.loginfo(f"➡️ 前进 {dist}m")
        move_cmd(lx=speed, duration=dur, pub=pub, rate=rate)
        stop(pub, rate)

        # 掉头
        rospy.loginfo("🔄 掉头 180°")
        move_cmd(az=TURN_SPEED, duration=turn_dur, pub=pub, rate=rate)
        stop(pub, rate)

        # 前进(返) — 车掉头后，往前走就是回去
        rospy.loginfo(f"⬅️ 前进 {dist}m (返回)")
        move_cmd(lx=speed, duration=dur, pub=pub, rate=rate)
        stop(pub, rate)

        # 掉头
        rospy.loginfo("🔄 掉头 180°")
        move_cmd(az=TURN_SPEED, duration=turn_dur, pub=pub, rate=rate)
        stop(pub, rate)

    rospy.loginfo("🏁 完成")
    stop(pub, rate)
