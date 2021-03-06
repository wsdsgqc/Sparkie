#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module ...

__author__ = "Magnus Kvendseth Øye"
__copyright__ = "Copyright 2019, Sparkie Quadruped Robot"
__credits__ = ["Magnus Kvendseth Øye", "Petter Drønnen", "Vegard Solheim"]
__version__ = "1.0.0"
__license__ = "MIT"
__maintainer__ = "Magnus Kvendseth Øye"
__email__ = "magnus.oye@gmail.com"
__status__ = "Development"
"""

# Importing packages
from __future__ import print_function
import rviz
from python_qt_binding import QtWidgets, QtCore, QtGui
from python_qt_binding.binding_helper import *
import cv2
import numpy as np
import requests
import json
from cv_bridge import CvBridge
import sys
import time
import rospy
import roslib
import os
import threading
import subprocess
from sensor_msgs.msg import Image
from std_msgs.msg import String, UInt8
from move_base_msgs.msg import MoveBaseActionGoal, MoveBaseActionFeedback, MoveBaseGoal
from actionlib_msgs.msg import GoalID, GoalStatusArray
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
import actionlib
from actionlib_msgs.msg import *
import datetime

roslib.load_manifest('rviz')


class InspectionWindow(QtWidgets.QDialog):
    """This window operates as the main interaction with the robot under inspection missions"""

    activate = QtCore.pyqtSignal(bool)

    def __init__(self):
        super(InspectionWindow, self).__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.ui = '../forms/manual.ui'
        self.mission_dir = '../instance/missions'
        loadUi(self.ui, self)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        self.layout = self.findChild(QtWidgets.QGridLayout, 'layout')

        self.table_row_tracker = 2
        self.num_goal_reached = 0

        # Image frames
        self.videoframe = self.findChild(QtWidgets.QLabel, 'videoFrame')
        self.topImageLabel = self.findChild(QtWidgets.QLabel, 'topImageLabel')
        self.middelImageLabel = self.findChild(QtWidgets.QLabel, 'middelImageLabel')
        self.bottomImageLabel = self.findChild(QtWidgets.QLabel, 'bottomImageLabel')

        # Buttons
        self.startVideoStreamBtn = self.findChild(QtWidgets.QPushButton, 'startVideoStreamBtn')
        self.stopVideoStreamBtn = self.findChild(QtWidgets.QPushButton, 'stopVideoStreamBtn')
        self.abortMissionBtn = self.findChild(QtWidgets.QToolButton, 'abortMissionBtn')
        self.inspectStatusBtn = self.findChild(QtWidgets.QPushButton, 'inspectStatusBtn')
        self.pauseMissionBtn = self.findChild(QtWidgets.QToolButton, 'pauseMissionBtn')
        self.stopMissionBtn = self.findChild(QtWidgets.QToolButton, 'stopMissionBtn')
        self.startMissionBtn = self.findChild(QtWidgets.QToolButton, 'startMissionBtn')
        self.refreshSelectMissionAreaBtn = self.findChild(QtWidgets.QToolButton, 'refreshSelectMissionAreaBtn')
        self.refreshSelectMissionBtn = self.findChild(QtWidgets.QToolButton, 'refreshSelectMissionBtn')
        self.inspectStatusBtn.hide()

        # Button connections
        self.startMissionBtn.clicked.connect(self.start_mission)
        self.pauseMissionBtn.clicked.connect(self.pause_mission)

        # Labels
        self.runninMissionLabel = self.findChild(QtWidgets.QLabel, 'runninMissionLabel')
        self.runningTaskLabel = self.findChild(QtWidgets.QLabel, 'runningTaskLabel')
        self.currentRunningMissionLabel = self.findChild(QtWidgets.QLabel, 'currentRunningMissionLabel')

        # Progressbars
        self.runningTaskProgressBar = self.findChild(QtWidgets.QProgressBar, 'runningTaskProgressBar')

        # Comboboxes
        self.videoSourceComboBox = self.findChild(QtWidgets.QComboBox, 'videoSourceComboBox')
        self.selectMissionAreaComboBox = self.findChild(QtWidgets.QComboBox, 'selectMissionAreaComboBox')
        self.selectMissionComboBox = self.findChild(QtWidgets.QComboBox, 'selectMissionComboBox')

        self.videoSourceComboBox.addItems(["Color", "Fisheye 1", "Fisheye 2","Infared 1", "Infared 2", ])
        self.selectMissionAreaComboBox.addItems(['', "Workshop", "University", "Demo 1","Demo 2", "Demo 3"])
        self.find_missions()

        # RVIZ
        self.visual_frame = rviz.VisualizationFrame()
        self.visual_frame.setSplashPath("")
        self.visual_frame.initialize()
        self.add_rviz_config()

        self.visual_frame.setMenuBar(None)
        self.visual_frame.setStatusBar(None)
        self.visual_frame.setHideButtonVisibility(True)

        self.layout.addWidget(self.visual_frame)

        self.manager = self.visual_frame.getManager()
        self.grid_display = self.manager.getRootDisplayGroup().getDisplayAt(0)

        self.plan = None
        self.missions = []
        self.column_images = [self.topImageLabel, self.middelImageLabel, self.bottomImageLabel]
        self.column_image_counter = 0

        # Tables
        self.tableWidget = self.findChild(QtWidgets.QTableWidget, 'tableWidget')
        self.tableWidget.setHorizontalHeaderLabels(['Time', 'Tag', 'Operation','Status', 'Value', 'Warning', 'Error'])
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.Stretch)
    
        # Top Buttons
        self.change_mode_btn = self.findChild(
            QtWidgets.QPushButton, 'changeModeBtn')
        self.exit_btn = self.findChild(QtWidgets.QPushButton, 'exitBtn')
        self.powerBtn = self.findChild(QtWidgets.QPushButton, 'powerBtn')
        self.emergency_btn = self.findChild(
            QtWidgets.QPushButton, 'emergencyBtn')

        # Status indicators
        self.signal_btn = self.findChild(QtWidgets.QPushButton, 'signalBtn')
        self.controller_battery_btn = self.findChild(
            QtWidgets.QPushButton, 'controllerBatteryBtn')
        self.battery_btn = self.findChild(QtWidgets.QPushButton, 'batteryBtn')
        self.health_btn = self.findChild(QtWidgets.QPushButton, 'healthBtn')

        # Button connections

        # Button shortcuts
        self.exit_btn.setShortcut("Ctrl+Q")

        # Stylesheets
        self.powerBtn.setStyleSheet(
            "QPushButton#powerBtn:checked {color:black; background-color: red;}")
        self.signal_btn.setStyleSheet(
            "QPushButton#signalBtn:checked {color:black; background-color: green;}")
        
        # ROS SUBSCRIBERS
        rospy.init_node('listener', anonymous=True)
        rospy.Subscriber('/d435/infra1/image_rect_raw', Image, self.image_callback)
        rospy.Subscriber('goal_reached', UInt8, self.result_callback)
        rospy.Subscriber('in_position', String, self.api_callback)

        self.show()

    def add_rviz_config(self):
        """Add rviz configurations from external file"""
        reader = rviz.YamlConfigReader()
        config = rviz.Config()
        reader.readFile(config, "../instance/Sparkie.rviz")
        self.visual_frame.load(config)

    def start_mission(self):
        """Start selected mission"""
        choice = QtWidgets.QMessageBox.question(self, 'Warning', 'Start new mission?', QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) 
        if choice == QtWidgets.QMessageBox.Yes:
            self.load_mission()
            self.startMissionBtn.setDisabled(True)
            self.refreshSelectMissionAreaBtn.setDisabled(True)
            self.refreshSelectMissionBtn.setDisabled(True)
            self.selectMissionAreaComboBox.setDisabled(True)
            self.selectMissionComboBox.setDisabled(True)
            self.runninMissionLabel.setText(self.selectMissionComboBox.currentText())
            self.currentRunningMissionLabel.setText(self.selectMissionComboBox.currentText())
            self.tableWidget.setItem(0,0, QtWidgets.QTableWidgetItem(str(datetime.datetime.fromtimestamp(rospy.get_time()))))
            self.tableWidget.setItem(0,1, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(0,2, QtWidgets.QTableWidgetItem('Starting Mission'))
            self.tableWidget.setItem(0,3, QtWidgets.QTableWidgetItem('Init'))
            self.tableWidget.setItem(0,4, QtWidgets.QTableWidgetItem('Success'))
            self.tableWidget.setItem(0,5, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(0,6, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(0,7, QtWidgets.QTableWidgetItem('N/A'))
            self.runningTaskLabel.setText('Starting Mission')
            self.tableWidget.setItem(1,0, QtWidgets.QTableWidgetItem(str(datetime.datetime.fromtimestamp(rospy.get_time()))))
            self.tableWidget.setItem(1,1, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(1,2, QtWidgets.QTableWidgetItem('Move to new waypoint'))
            self.tableWidget.setItem(1,3, QtWidgets.QTableWidgetItem('Sent'))
            self.tableWidget.setItem(1,4, QtWidgets.QTableWidgetItem('Ongoing'))
            self.tableWidget.setItem(1,5, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(1,6, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(1,7, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(2,0, QtWidgets.QTableWidgetItem(''))
            self.runningTaskLabel.setText('Move to new waypoint')
            self.post_goal()
        else:
            pass
    
    def result_callback(self, data):
        """Goal reached callback"""
        if data.data:
            self.runningTaskProgressBar.setValue(self.num_goal_reached)
            self.num_goal_reached += 1
            print(self.num_goal_reached)
            print("Goal Reached, ready for new one")
            self.tableWidget.setItem(self.table_row_tracker, 0, QtWidgets.QTableWidgetItem(str(datetime.datetime.fromtimestamp(rospy.get_time()))))
            self.tableWidget.setItem(self.table_row_tracker, 1, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(self.table_row_tracker, 2, QtWidgets.QTableWidgetItem('Reached waypoint'))
            self.tableWidget.setItem(self.table_row_tracker, 3, QtWidgets.QTableWidgetItem('Success'))
            self.tableWidget.setItem(self.table_row_tracker, 4, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(self.table_row_tracker, 5, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(self.table_row_tracker, 6, QtWidgets.QTableWidgetItem('N/A'))
            self.runningTaskLabel.setText('Reached waypoint')
            self.table_row_tracker += 1

    def image_callback(self, data):
        """Image callback"""
        #rospy.loginfo(rospy.get_caller_id() + "I heard %s", data.data) 
        rgb_image = CvBridge().imgmsg_to_cv2(data, desired_encoding="rgb8")
        height, width, channel = rgb_image.shape
        bytesPerLine = 3 * width
        qImg = QtGui.QImage(rgb_image.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888)
        self.videoframe.setPixmap(QtGui.QPixmap(qImg))
    
    def api_callback(self, data):
        """API callback from cloud"""
        print("Robot in position")
        self.tableWidget.setItem(self.table_row_tracker, 0, QtWidgets.QTableWidgetItem(str(datetime.datetime.fromtimestamp(rospy.get_time()))))
        self.tableWidget.setItem(self.table_row_tracker, 1, QtWidgets.QTableWidgetItem('N/A'))
        self.tableWidget.setItem(self.table_row_tracker, 2, QtWidgets.QTableWidgetItem('Move to new waypoint'))
        self.tableWidget.setItem(self.table_row_tracker, 3, QtWidgets.QTableWidgetItem('Sent'))
        self.tableWidget.setItem(self.table_row_tracker, 4, QtWidgets.QTableWidgetItem('N/A'))
        self.tableWidget.setItem(self.table_row_tracker, 5, QtWidgets.QTableWidgetItem('N/A'))
        self.tableWidget.setItem(self.table_row_tracker, 6, QtWidgets.QTableWidgetItem('N/A'))
        self.runningTaskLabel.setText('Move to new waypoint')
        self.table_row_tracker += 1
        command = 'python post_goal.py %s' % self.num_goal_reached
        _id = rospy.get_caller_id()
        _class = self.plan[self.num_goal_reached-1]
        print(_class)
        if len(_class) > 3:
            self.tableWidget.setItem(self.table_row_tracker, 0, QtWidgets.QTableWidgetItem(str(datetime.datetime.fromtimestamp(rospy.get_time()))))
            self.tableWidget.setItem(self.table_row_tracker, 1, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(self.table_row_tracker, 2, QtWidgets.QTableWidgetItem('Move head to position'))
            self.tableWidget.setItem(self.table_row_tracker, 3, QtWidgets.QTableWidgetItem('Ongoing'))
            self.tableWidget.setItem(self.table_row_tracker, 4, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(self.table_row_tracker, 5, QtWidgets.QTableWidgetItem('N/A'))
            self.tableWidget.setItem(self.table_row_tracker, 6, QtWidgets.QTableWidgetItem('N/A'))
            self.runningTaskLabel.setText('Move head to position')
            self.table_row_tracker += 1
            time.sleep(10)
            self.tableWidget.setItem(self.table_row_tracker-1, 3, QtWidgets.QTableWidgetItem('Complete'))
            self.post_goal()
            print("New goal sent, waiting for database to update")
            time.sleep(8)
            URL = 'http://dr0nn1.ddns.net:5000/%s/1' % _class
            response = requests.get(URL)
            content = response.json()
            tag = 'N/A'
            value = 'N/A'
            warning = 'N/A'
            alarm = 'N/A'
            value = 'N/A'

            if _class == 'manometers':
                value = float(content['value'])
                warning_low = float(content['low_warning_limit'])
                warning_high = float(content['high_warning_limit'])
                alarm_low = float(content['low_alarm_limit'])
                alarm_high = float(content['high_alarm_limit'])

                if value > warning_high and value < alarm_high:
                    warning = 'Warning high'
                elif value < warning_low and value > alarm_low:
                    warning = 'Warning low'
                elif value > alarm_high:
                    alarm = 'Alarm high'
                elif value < alarm_low:
                    alarm = 'Alarm low'
                tag = content['tag']
                
            if _class == 'valve':
                normal_condition = content['normal_condition']
                should_be = content['is_open']
                tag = content['tag']
                if value is not should_be:
                    warning = 'Not in position'

            IMG = content['img'].encode('latin1')
            rgb_image = np.fromstring(IMG, dtype=np.uint8).reshape((480, 640, 3))
            height, width, channel = rgb_image.shape
            bytesPerLine = 3 * width
            qImg = QtGui.QImage(rgb_image.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888)
            self.column_images[self.column_image_counter].setPixmap(QtGui.QPixmap(qImg))
            self.tableWidget.setItem(self.table_row_tracker, 0, QtWidgets.QTableWidgetItem(str(datetime.datetime.fromtimestamp(rospy.get_time()))))
            self.tableWidget.setItem(self.table_row_tracker, 1, QtWidgets.QTableWidgetItem(tag))
            self.tableWidget.setItem(self.table_row_tracker, 2, QtWidgets.QTableWidgetItem('Inspecting equipment'))
            self.tableWidget.setItem(self.table_row_tracker, 3, QtWidgets.QTableWidgetItem('Complete'))
            self.tableWidget.setItem(self.table_row_tracker, 4, QtWidgets.QTableWidgetItem(value))
            self.tableWidget.setItem(self.table_row_tracker, 5, QtWidgets.QTableWidgetItem(warning))
            self.tableWidget.setItem(self.table_row_tracker, 6, QtWidgets.QTableWidgetItem(alarm))
            self.runningTaskLabel.setText('Inspecting equipment')
            self.table_row_tracker += 1
            self.column_image_counter += 1
            if self.column_image_counter > 2:
                self.column_image_counter = 0
        else:
            time.sleep(2)
            self.post_goal()

    def post_goal(self):
        """Post new waypoint to subsystem"""
        th = threading.Thread(target=self._post_goal)
        th.start()

    def _post_goal(self):
        """Post new waypoint to subsystem"""
        print('Posting new goal to agent')
        self.tableWidget.setItem(self.table_row_tracker, 0, QtWidgets.QTableWidgetItem(str(datetime.datetime.fromtimestamp(rospy.get_time()))))
        self.tableWidget.setItem(self.table_row_tracker, 1, QtWidgets.QTableWidgetItem('N/A'))
        self.tableWidget.setItem(self.table_row_tracker, 2, QtWidgets.QTableWidgetItem('Move to new waypoint'))
        self.tableWidget.setItem(self.table_row_tracker, 3, QtWidgets.QTableWidgetItem('Sent'))
        self.tableWidget.setItem(self.table_row_tracker, 4, QtWidgets.QTableWidgetItem('N/A'))
        self.tableWidget.setItem(self.table_row_tracker, 5, QtWidgets.QTableWidgetItem('N/A'))
        self.tableWidget.setItem(self.table_row_tracker, 6, QtWidgets.QTableWidgetItem('N/A'))
        self.runningTaskLabel.setText('Move to new waypoint')
        self.table_row_tracker += 1
        command = 'python post_goal.py %s' % self.num_goal_reached
        subprocess.call(command, shell=True)

    def power_on(self):
        """Turn on interface"""
        active = self.powerBtn.isChecked()
        if active:
            self.activate.emit(True)
        else:
            self.activate.emit(False)

    def close_window(self):
        """Close window Ctrl+Q"""
        self.close()

    def turn_robot_off(self):
        pass
    
    def pause_mission(self):
        pass
    
    def load_mission(self):
        """Preload missions"""
        mission = self.missions[self.selectMissionComboBox.currentIndex()]
        with open(mission, 'r') as file:
            self.plan = file.read().split(',')
    
    def find_missions(self):
        """Find missionfiles in mission directory"""
        for file in os.listdir(self.mission_dir):
            if file.endswith(".txt"):
                self.missions.append(os.path.join(self.mission_dir, file))
                self.selectMissionComboBox.addItem(file)
