#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
odom_tf_broadcaster.py
从 /odom (EKF 融合后的里程计) 读取位姿，发布 TF: odom → base_footprint
用于小车导航时 AMCL 的 map→odom TF 链补全
"""
import rospy
import tf
from nav_msgs.msg import Odometry

class OdomTFBroadcaster:
    def __init__(self):
        self.tf_broadcaster = tf.TransformBroadcaster()
        self.sub = rospy.Subscriber('/odom', Odometry, self.odom_callback)

    def odom_callback(self, msg):
        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation
        self.tf_broadcaster.sendTransform(
            (pos.x, pos.y, pos.z),
            (ori.x, ori.y, ori.z, ori.w),
            msg.header.stamp,
            "base_footprint",
            "odom"
        )

if __name__ == '__main__':
    rospy.init_node('odom_tf_broadcaster')
    node = OdomTFBroadcaster()
    rospy.spin()
