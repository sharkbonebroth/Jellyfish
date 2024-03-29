#!/usr/bin/env python  
import math
from copy import deepcopy

from numpy.core.fromnumeric import std
from numpy.lib.function_base import diff
import rospy

import geometry_msgs.msg
import tf.transformations
import mav_msgs.msg
import sensor_msgs.msg

speed = 0.75
angle_speed = 1.570795
goal_pose = None
intermediate_goal_positions = []
intermediate_goal_pose = geometry_msgs.msg.Pose() 
intermediate_goal_pose.position.x = 0
intermediate_goal_pose.position.y = 0
intermediate_goal_pose.position.z = 0
intermediate_goal_pose.orientation.x = 0
intermediate_goal_pose.orientation.y = 0
intermediate_goal_pose.orientation.z = 0
intermediate_goal_pose.orientation.w = 1
current_pose = deepcopy(intermediate_goal_pose)
moving_towards_goal = False
prev_intermediate_z = 0

def handle_goal(msg):
    global moving_towards_goal
    global goal_pose
    moving_towards_goal = True
    new_goal_pose = geometry_msgs.msg.Pose()
    new_orientation = tf.transformations.quaternion_from_euler(0, 0, msg.yaw)
    new_goal_pose.orientation.x = new_orientation[0]
    new_goal_pose.orientation.y = new_orientation[1]
    new_goal_pose.orientation.z = new_orientation[2]
    new_goal_pose.orientation.w = new_orientation[3]
    new_goal_pose.position.x = msg.position.x
    new_goal_pose.position.y = msg.position.y
    new_goal_pose.position.z = msg.position.z
    goal_pose = new_goal_pose
    generate_intermediate_goal_positions(new_goal_pose)
    


def difference_between_position_and_goal(position, goal):
    #Returns a list of difference information, in the following order
    # Index 0: Distance difference, 
    # Index 1: Magnitude of yaw difference, 
    # Index 2: x difference, 
    # Index 3: y difference, 
    # Index 4: z difference, 
    x_difference = goal.position.x - position.position.x
    y_difference = goal.position.y - position.position.y
    z_difference = goal.position.z - position.position.z
    distance_difference = math.sqrt(x_difference**2 + y_difference**2 + z_difference**2)
    position_quaternion = [position.orientation.x, position.orientation.y, position.orientation.z, position.orientation.w]
    goal_quaternion = [goal.orientation.x, goal.orientation.y, goal.orientation.z, goal.orientation.w]
    yaw_difference = tf.transformations.euler_from_quaternion(goal_quaternion)[2] - tf.transformations.euler_from_quaternion(position_quaternion)[2]
    return [distance_difference, yaw_difference, x_difference, y_difference, z_difference]

def generate_intermediate_goal_positions(msg):
    global intermediate_goal_positions
    initial_pose = deepcopy(current_pose)
    intermediate_goal_positions = []
    difference = difference_between_position_and_goal(initial_pose, msg)
    x_step = speed * math.sqrt(difference[2]**2 / difference[0] **2) * (lambda x: 1 if x >= 0 else -1)(difference[2])
    y_step = speed * math.sqrt(difference[3]**2 / difference[0] **2) * (lambda x: 1 if x >= 0 else -1)(difference[3])
    z_step = speed * math.sqrt(difference[4]**2 / difference[0] **2) * (lambda x: 1 if x >= 0 else -1)(difference[4])
    most_recent_generated_goal_position =  initial_pose.position
    while most_recent_generated_goal_position != msg.position:
        step = False
        if abs(msg.position.x - most_recent_generated_goal_position.x) > abs(x_step):
            step = True
        if abs(msg.position.y - most_recent_generated_goal_position.y) > abs(y_step):
            step = True
        if abs(msg.position.z - most_recent_generated_goal_position.z) > abs(z_step):
            step = True
        if step:
            most_recent_generated_goal_position.x += x_step
            most_recent_generated_goal_position.y += y_step
            most_recent_generated_goal_position.z += z_step
        else:
            most_recent_generated_goal_position = msg.position
        new_goal_position = deepcopy(most_recent_generated_goal_position)
        intermediate_goal_positions.append(new_goal_position)
        

def generate_new_intermediate_goal_pose(current_position):
    global intermediate_goal_pose
    global moving_towards_goal
    new_intermediate_goal_pose = intermediate_goal_pose

    difference = difference_between_position_and_goal(current_position, intermediate_goal_pose)
    if (difference[0] < speed):
        if intermediate_goal_positions != []:
            new_intermediate_goal_pose.position = intermediate_goal_positions.pop(0)
    if (abs(difference[1]) < angle_speed):
        new_intermediate_goal_pose.orientation = goal_pose.orientation
    else:
        current_pose_quaternion = [current_position.orientation.x, current_position.orientation.y, current_position.orientation.z, current_position.orientation.w]
        yaw = tf.transformations.euler_from_quaternion(current_pose_quaternion)[2] + angle_speed * (lambda x: 1 if x >= 0 else -1)(difference[1])
        new_intermediate_goal_pose_orientation = tf.transformations.quaternion_from_euler(0, 0, yaw)
        new_intermediate_goal_pose.orientation.x = new_intermediate_goal_pose_orientation[0]
        new_intermediate_goal_pose.orientation.y = new_intermediate_goal_pose_orientation[1]
        new_intermediate_goal_pose.orientation.z = new_intermediate_goal_pose_orientation[2]
        new_intermediate_goal_pose.orientation.w = new_intermediate_goal_pose_orientation[3]
    intermediate_goal_pose = new_intermediate_goal_pose
    if new_intermediate_goal_pose == goal_pose:
        moving_towards_goal = False

def handle_current_pose(msg):
    global moving_towards_goal
    global current_pose
    current_pose = msg
    if not moving_towards_goal:
        pass
    else:
        generate_new_intermediate_goal_pose(msg)


def goal_broadcaster():
    pub = rospy.Publisher("command/pose", geometry_msgs.msg.PoseStamped, queue_size=1)
    r = rospy.Rate(5)
    while not rospy.is_shutdown():
        global intermediate_goal_pose
        new_goal = geometry_msgs.msg.PoseStamped()
        new_goal.pose = intermediate_goal_pose
        new_goal.header.stamp = rospy.Time.now()
        new_goal.header.frame_id = "world"
        pub.publish(new_goal)
        r.sleep()

if __name__ == '__main__':
    rospy.init_node("goal_receiver")
    rospy.Subscriber("ground_truth/pose",
                    geometry_msgs.msg.Pose,
                    handle_current_pose)
    rospy.Subscriber("position_command/trajectory",
                    mav_msgs.msg.CommandTrajectory,
                    handle_goal)
    goal_broadcaster()
    rospy.spin()
