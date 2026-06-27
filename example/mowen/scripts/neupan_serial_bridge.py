#!/usr/bin/env python3
"""
NeuPAN 专用串口桥 — 替代 newt.py 的高频版本

协议: 与 newt.py 完全一致 (header 0xAABB0A1202, ×1000, 小端序, 115200)
改进: 无打印, 整帧批量写入, 支持 55Hz 无卡顿
"""
import serial
import rospy
from geometry_msgs.msg import Twist

HEADER = b'\xAA\xBB\x0A\x12\x02'
INIT  = b'\x11\x00\x00\x00\x00\x00\x00\x00\x00'
TERM  = b'\x00'

def speed_to_bytes(val):
    """Convert float speed to 2-byte little-endian, ×1000, two's complement for negative"""
    v = int(round(val * 1000))
    if v < 0:
        v = v & 0xFFFF
    return bytes([v & 0xFF, (v >> 8) & 0xFF])  # lo, hi

def callback(msg):
    x = msg.linear.x
    y = msg.linear.y
    th = msg.angular.z
    frame = HEADER + speed_to_bytes(x) + speed_to_bytes(y) + speed_to_bytes(th) + TERM
    try:
        ser.write(frame)
    except:
        pass

if __name__ == '__main__':
    rospy.init_node('neupan_serial_bridge')
    ser = serial.Serial('/dev/carserial', 115200, timeout=1)
    rospy.sleep(0.3)
    ser.write(INIT)
    rospy.Subscriber('/cmd_vel', Twist, callback, queue_size=1)
    rospy.loginfo('neupan_serial_bridge ready - 55Hz OK')
    rospy.spin()
