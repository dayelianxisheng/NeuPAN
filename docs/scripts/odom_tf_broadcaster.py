#!/usr/bin/env python
# Subscribe /odom_raw, broadcast odom -> base_footprint TF.
import rospy
import tf
from nav_msgs.msg import Odometry

br = None

def callback(msg):
    br.sendTransform(
        (msg.pose.pose.position.x, msg.pose.pose.position.y, msg.pose.pose.position.z),
        (msg.pose.pose.orientation.x, msg.pose.pose.orientation.y,
         msg.pose.pose.orientation.z, msg.pose.pose.orientation.w),
        msg.header.stamp,
        "base_footprint",
        "odom"
    )

if __name__ == '__main__':
    rospy.init_node('odom_tf_broadcaster')
    br = tf.TransformBroadcaster()
    rospy.Subscriber('/odom_raw', Odometry, callback)
    rospy.loginfo('odom_tf_broadcaster ready')
    rospy.spin()
