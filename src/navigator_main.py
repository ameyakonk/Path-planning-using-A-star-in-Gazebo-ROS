import sys
import rospy
import numpy as np
import random
import cv2
import math

from std_msgs.msg import String
from std_srvs.srv import Empty
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from tf.transformations import euler_from_quaternion, quaternion_from_euler

class Node:
    def __init__(self, f_, g_, theta_,  parent_, parent_index):
        
        self.theta = theta_
        self.f = f_
        self.g = g_
        self.parent = parent_
        self.parent_index = parent_index


def free_space(c, r):
    space = np.ndarray((1000,1000),dtype=Node)
 
    for x in range(1000):
        for y in range(1000):
            parent = np.array([-1, -1])
            space[x, y] = Node(np.inf, 0, 0, parent, -1)

            if ((x - 200)**2 + (y - 200)**2 < (100+c+r)**2) or ((x - 200)**2 + (y - 800)**2 < (100+c+r)**2) or (((425-c) < y < (575+c)) and ((25-c-r) < x < (175+c+r))) or (((425-c-r) < y < (575+c+r)) and ((375-c-r) < x < (625+c+r))) or (((200-c-r) < y < (400+c+r)) and ((725-c-r) < x < (875+c+r))):

                space[x, y] = Node(-1, 0, 0, parent, -1)
                
    return space


def visualize(c):

    vis = np.zeros((1000, 1000, 3), np.uint8)

    for x in range(1000):
        for y in range(1000):

            if ((x - 200)**2 + (y - 200)**2 < (100+c)**2) or ((x - 200)**2 + (y - 800)**2 < (100+c)**2) or (((425-c) < y < (575+c)) and ((25-c) < x < (175+c))) or (((425-c) < y < (575+c)) and ((375-c) < x < (625+c))) or (((200-c) < y < (400+c)) and ((725-c) < x < (875+c))):
                
                vis[x][y] = (0, 255, 255)

            if ((x - 200)**2 + (y - 200)**2 < 100**2) or ((x - 200)**2 + (y - 800)**2 < 100**2) or ((425 < y < 575) and (25 < x < 175)) or ((425 < y < 575) and (375 < x < 625)) or ((200 < y < 400) and (725 < x < 875)):

                vis[x][y] = (0, 0, 255)

    return vis


def isValid(point, space):
    if (not (0 < point[0] < 1000)) or (not (0 < point[1] < 1000)) or (space[point[0], point[1]].f == -1):
        return False
    return True


def isDestination(point, goal):
    return np.array_equal(point, goal)


def rot2trans(Xi, Yi, Thetai, UL, UR):
    t = 0
    r = 6.6
    L = 16
    dt = 0.1
    Xn = Xi
    Yn = Yi
    Thetan = 3.14 * Thetai / 180
    while t < 1:
        t = t + dt
        Xs = Xn
        Ys = Yn
        Xn += round(0.5 * r * (UL + UR) * math.cos(Thetan) * dt)
        Yn += round(0.5 * r * (UL + UR) * math.sin(Thetan) * dt)
        Thetan += (r / L) * (UR - UL) * dt
    Thetan = 180 * (Thetan) / 3.14
    return Xn, Yn, Thetan


def childnodes(x, y, theta, action, src, goal, space):

    childnodes = []
    parent_g = space[x, y].g

    for i in range(len(action)):
        childx, childy, childtheta = rot2trans(x, y, theta, action[i][0], action[i][1])
        childcost, g = heuristic(childx, childy, goal, parent_g, x, y)
        childnodes.append([childx, childy, childtheta, i, childcost, g])

    return childnodes


def heuristic(x, y, goal, parent_g, p_x, p_y):

    h = (math.sqrt(((x - goal[0])**2) + ((y - goal[1])**2)))
    g = parent_g + (math.sqrt(((x - p_x)**2) + ((y - p_y)**2)))

    return (h + g), g

def checkThreshold(point, goal):
    threshold = 30
    return (point[0] - goal[0])*(point[0] - goal[0]) + (point[1] - goal[1])*(point[1] - goal[1]) <= threshold*threshold



def plot_curve(vis, Xi, Yi, Thetai, UL, UR):
    t = 0
    r = 6.6
    L = 16
    dt = 0.1
    Xn = Xi
    Yn = Yi
    Thetan = 3.14 * Thetai / 180

    while t < 1:
        t = t + dt
        Xs = Xn
        Ys = Yn
        Xn += round(0.5 * r * (UL + UR) * math.cos(Thetan) * dt)
        Yn += round(0.5 * r * (UL + UR) * math.sin(Thetan) * dt)
        Thetan += (r / L) * (UR - UL) * dt
        cv2.line(vis, (Yn, Xn) , (Ys, Xs), (255, 255, 255), 1)


def A_star(src, goal, action, clearance, radius):

    vis = visualize(clearance)
    cv2.circle(vis, (src[1], src[0]), 3, (203, 192, 255), -1)
    cv2.circle(vis, (goal[1], goal[0]), 3, (203, 192, 255), -1)
    
    src_x = src[0]
    src_y = src[1]
    
    space = free_space(clearance, radius)
    space[src_x, src_y].f = 0
    space[src_x, src_y].g = 0
    space[src_x, src_y].theta = src[2]
    space[src_x, src_y].parent = np.array([src_x, src_y])

    openList = {}
    openList[(src_x, src_y)] = space[src_x, src_y].f
    closedList = np.zeros((1000, 1000))
    
   
    while(not len(openList) == 0):

        point = min(openList, key=openList.get)
        openList.pop(point, None)

        i = point[0]
        j = point[1]
        theta = space[i, j].theta
        successorList = childnodes(i, j, theta, action, src, goal, space)
        closedList[i, j] = 1
        cv2.circle(closedList, (j, i), 10, 1, -1)
        
        for data in successorList:
            new_i = data[0]
            new_j = data[1]
            theta_new = data[2]
            parent_index = data[3]
            f_new = data[4]
            g_new = data[5]

            cur_point = np.array([new_i, new_j])
            
            if(isValid(cur_point, space)):
                if(checkThreshold(cur_point, goal[0:2])):
                    space[new_i, new_j].parent = np.array([i, j])
                    traverseList, actionsList = backtrack(cur_point, src, space, goal[0:2])
                    print()
                    print("-------------------------------------")
                    print("Optimal Path Found, Displaying Output")
                    print("-------------------------------------")
                   # visualize_path(traverseList, vis, radius)
                    #cv2.destroyAllWindows()
                    print()
                    print("-------------------------------------")
                    print("Destination Reached")
                    print("-------------------------------------")
                    return traverseList, actionsList

                elif closedList[new_i, new_j] == 0:
                    if space[new_i, new_j].f == np.inf or space[new_i, new_j].f > f_new:
                        openList[new_i, new_j] = f_new
                        space[new_i, new_j].f = f_new
                        space[new_i, new_j].g = g_new
                        space[new_i, new_j].theta = theta_new
                        space[new_i, new_j].parent_index = parent_index
                        space[new_i, new_j].parent = np.array([i, j])
                        # cv2.line(vis, (new_j, new_i) , (j, i), (255, 255, 255), 1)
                        plot_curve(vis, i, j, theta, action[parent_index][0], action[parent_index][1])

        vis = cv2.rotate(vis, cv2.ROTATE_90_COUNTERCLOCKWISE)

        cv2.imshow('A*', vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            return 0

        vis = cv2.rotate(vis, cv2.ROTATE_90_CLOCKWISE)


def backtrack(cur_point, src, space, goal):
    space_ = space.copy()
    x = cur_point[0].copy()
    y = cur_point[1].copy()

    traverseList = []
    actionsList = []

    traverseList.append((goal[0], goal[1]))
    while(not (x == src[0] and y == src[1])):
        temp = space_[x,y].parent[0].copy()
        y = space_[x,y].parent[1].copy()
        x = temp
        parent_index = space_[x,y].parent_index
        traverseList.append((x,y))
        actionsList.append(parent_index)

    traverseList.append((src[0], src[1]))
    traverseList.reverse()

    return traverseList, actionsList

def visualize_path(traverseList, vis, radius):

    while(len(traverseList) > 1):
        vis_ = vis.copy()
        y = traverseList.pop(0)[0]
        x = traverseList.pop(0)[1]
        cv2.circle(vis_, (x, y) , radius, (0, 255, 0), -1)
        vis_ = cv2.rotate(vis_, cv2.ROTATE_90_COUNTERCLOCKWISE)
        cv2.imshow('A*', vis_)
        if cv2.waitKey(100) & 0xFF == ord('q'):
            return 0
        vis_ = cv2.rotate(vis_, cv2.ROTATE_90_CLOCKWISE)
    cv2.destroyAllWindows()

def user_input():

    # src_x = 100*int((input("Enter x coordinaate of source point: ")))
    # src_y = 100*int((input("Enter y coordinaate of source point: ")))
    # src_theta = int((input("Enter orientation at source point: ")))

    # goal_x = 100*int((input("Enter x coordinaate of goal point: ")))
    # goal_y = 100*int((input("Enter y coordinaate of goal point: ")))
    # goal_theta = int((input("Enter orientation at goal point: ")))

    # length = round(100*float((input("Enter length of step between 0 and 10: "))))
    # clearance = round(100*float((input("Enter clearance space width: "))))
    # radius = round(100*float((input("Enter radius of robot: "))))

    src_x = 100*int((1))
    src_y = 100*int((1))
    src_theta = 0

    goal_x = 100*int((9))
    goal_y = 100*int((9))
    goal_theta = 0

    length = round(100*float((0.2)))
    clearance = round(100*float((0.2)))
    # radius = round(100*float((0.1)))
    radius = 10

    actions = [[5,5], [10,10],[5,0],[0,5],[5,10],[10,5]]

    space = free_space(clearance, radius)
    if not (isValid([src_x, src_y], space) and isValid([goal_x, goal_y], space)):
        return None, None, None, None, None 

    return np.array([src_x, src_y, src_theta]), np.array([goal_x, goal_y, goal_theta]), actions, clearance, radius


def nav_main():

    print("############################################# Processing #############################################")
    src, goal, actions, clearance, radius = user_input()

    # if(length == None):
    #     print("Invalid input, try again")
    #     return

    # src = [1, 1, 0]
    # goal = [9, 9, 0]
    # length = 0.2
    # clearance = 0.2
    # radius = 0.1

    return A_star(src, goal, actions, clearance, radius)

x_pose = 0
y_pose = 0
yaw = 0


def callback(msg):
    global x_pose
    global y_pose
    global yaw
    x_pose = float(msg.pose.pose.position.x)
    y_pose = float(msg.pose.pose.position.y)
    orientation_q = msg.pose.pose.orientation
    orientation_list = [orientation_q.x, orientation_q.y, orientation_q.z, orientation_q.w]
    (roll, pitch, yaw) = euler_from_quaternion (orientation_list)

def isReached(point, cur_pose):
    radius = 0.05
 #   print(cur_pose)
    if(point[0]-cur_pose[0])**2 + (point[1]-cur_pose[1])**2 <= radius**2:
        return True
    return False

i = 0

def Turtlebot_traverse(velocity_publisher, traverse_list):
    global i 

    kp_ang = 2
    kp_dist = 1.5
    desired_ang = math.atan((traverse_list[i][1] - y_pose)/((traverse_list[i][0] - x_pose) + 1e-07))

    distance = (traverse_list[i][0]-x_pose) + (traverse_list[i][1]-y_pose)
    dist_correction = distance*kp_dist

    ang_difference = desired_ang - (yaw)

    # print("traverse_list",traverse_list[i])
    # print("pose",(x_pose, y_pose))
    # print("desired_ang",desired_ang)
    # print("ang_difference",ang_difference)
    ang_correction = ang_difference*kp_ang

    vel_msg = Twist()
    vel_msg.linear.x = 0.2
    vel_msg.angular.z = ang_correction
    velocity_publisher.publish(vel_msg)

    if isReached(traverse_list[i], (x_pose, y_pose)):
        print((x_pose, y_pose))
        print(traverse_list[i])
        print("traverse_point reached")
        if i == len(traverse_list) - 1:
            print("Destination Reached")
            vel_msg.linear.x = 0.0
            vel_msg.angular.z = 0.0
            velocity_publisher.publish(vel_msg)
            exit()
        i += 1
   

def main(args):

  rospy.init_node('navigator', anonymous=True)
  velocity_publisher = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
  odom_sub = rospy.Subscriber('/odom', Odometry, callback)
 
  traverse_list, actionsList = nav_main()
  traverse_list = np.asarray(traverse_list)/100 - 5
 # cv2.destroyAllWindows()
  print(traverse_list)
  print()  
#   print((traverse_list[2][1] - y_pose)/((traverse_list[2][0] - x_pose) + 1e0-7))
  while (not rospy.is_shutdown()):

    try:

        Turtlebot_traverse(velocity_publisher, traverse_list)

    except KeyboardInterrupt:
        print("Shutting down")


if __name__ == '__main__':
    main(sys.argv)

