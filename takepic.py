#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time, os
from time import sleep
import json, datetime
import logging
import subprocess
import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

from libraryCH.device.camera import PICamera
from libraryCH.device.lcd import ILI9341


debugPrint = True
doorPin = 17

lcdDisplay = False
#LCD顯示設定------------------------------------
if(lcdDisplay==True):
    lcd = ILI9341(LCD_size_w=240, LCD_size_h=320, LCD_Rotate=90)

#開機及螢幕保護畫面
if(lcdDisplay==True):
    lcd.displayImg("rfidbg.jpg")

#是否拍照?
takePhoto = False

#MQTT設定---------------------------------------
ChannelPublish = "Door-camera"
MQTTuser = "chtseng"
MQTTpwd = "chtseng"
MQTTaddress = "akai-chen-pc3.sunplusit.com.tw"
MQTTport = 1883
MQTTtimeout = 60

#拍照設定--------------------------------------
#儲放相片的主目錄
picturesPath = "/var/www/html/rfidface/"
#相機旋轉角度
cameraRotate = 180
#拍攝的相片尺寸
#photoSize = (1280, 720)
photoSize = (2592, 1944)
#一次要連拍幾張
numPics = 10
#間隔幾毫秒
picDelay = 0.5 

#---------------------------------------------------------
#You don't have to modify the code below------------------
#---------------------------------------------------------
GPIO.setup(doorPin, GPIO.OUT)
GPIO.output(doorPin, 0)

if(takePhoto==True):
    camera = PICamera()
    camera.CameraConfig(rotation=cameraRotate)  
    camera.cameraResolution(resolution=photoSize)

#LCD設定
lcd_LineNow = 0
lcd_lineHeight = 30  #行的高度
lcd_totalLine = 8  # LCD的行數 (320/30=8)
screenSaverNow = False

#上次讀取到TAG的內容和時間
lastUIDRead = ""
lastTimeRead = time.time()


#logging記錄
logger = logging.getLogger('msg')
hdlr = logging.FileHandler('/home/pi/RFIDcamera/msg.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

#判斷是否為JSON格式
def is_json(myjson):
    try:
        json_object = json.loads(myjson)

    except ValueError:
        return False

    return True

#將行數轉為pixels
def lcd_Line2Pixel(lineNum):
    return lcd_lineHeight*lineNum

#LCD移到下一行, 若超過設定則清螢幕並回到第0行
def lcd_nextLine():
    global lcd_LineNow
    lcd_LineNow+=1
    if(lcd_LineNow>(lcd_totalLine-1)):
        lcd.displayClear()
        lcd_LineNow = 0

#LCD顯示刷卡內容
def displayUser(empNo, empName, timeString, uid):
    global lcd_LineNow

    if(debugPrint==True): print ("lcd_LineNow={}".format(lcd_LineNow))
    #st = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M')
    if(lcd_LineNow>0): lcd_nextLine()

    lcd.displayText("cfont1.ttf", fontSize=20, text=timeString, position=(lcd_Line2Pixel(lcd_LineNow), 180), fontColor=(253,244,6) )
    lcd.displayText("cfont1.ttf", fontSize=20, text=empNo, position=(lcd_Line2Pixel(lcd_LineNow), 110) )
    lcd.displayText("cfont1.ttf", fontSize=26, text=empName, position=(lcd_Line2Pixel(lcd_LineNow), 10) )
    lcd_nextLine()
    lcd.displayText("cfont1.ttf", fontSize=22, text=uid, position=(lcd_Line2Pixel(lcd_LineNow), 30), fontColor=(88,88,87) )

def takePictures(saveFolder="others"):
    global picDelay, numPics, picturesPath

    if(os.path.isdir(picturesPath+saveFolder)==False):
        os.makedirs(picturesPath+saveFolder)

    savePath = picturesPath + saveFolder + "/" + str(time.time())
    for i in range(0,numPics):
        camera.takePicture(savePath + "-" + str(i) + ".jpg")
        logger.info("TakePicture " + str(i) + " to " + savePath + "-" + str(i) + ".jpg")
        time.sleep(picDelay)

def openDoor():
    global doorPin

    GPIO.output(doorPin, 1) 
    sleep(0.3)
    GPIO.output(doorPin, 0)   

def on_connect(mosq, obj, rc):
    mqttc.subscribe("Door-camera", 0)
    if(debugPrint==True): print("rc: " + str(rc))

def on_message(mosq, obj, msg):
    global message, screenSaverNow
    #print(msg.topic + "/ " + str(msg.qos) + "/ " + str(msg.payload))
    msgReceived = str(msg.payload.decode("utf-8"))
    if(debugPrint==True): print ("Received: " + msgReceived)
    logger.info("MQTT received: " + msgReceived)
    lastTimeRead = time.time()


    if(is_json(msgReceived)==True):
        jsonReply = json.loads(msgReceived)
        screenSaverNow = False

        if(debugPrint==True): print('Time:'+jsonReply["Time"]+'  EmpNo:'+jsonReply["EmpNo"]+'  EmpCName:'+jsonReply["EmpCName"]+' DeptNo:'+jsonReply["DeptNo"])
        logger.info('Time:'+jsonReply["Time"]+'  EmpNo:'+jsonReply["EmpNo"]+'  EmpCName:'+jsonReply["EmpCName"]+' DeptNo:'+jsonReply["DeptNo"])

        if(lcdDisplay==True):
            displayUser(jsonReply["EmpNo"], jsonReply["EmpCName"], jsonReply["Time"], jsonReply["Uid"])

        if(takePhoto==True):
            takePictures(jsonReply["EmpNo"])

        if(jsonReply["TagType"]=='E'):
            #subprocess.Popen(['omxplayer', '--no-osd', 'bell.mp3'])
            openDoor()
            subprocess.call(["omxplayer", "--no-osd", "bell.mp3"])
            #os.system('omxplayer --no-osd bell.mp3')
        elif(jsonReply["TagType"]=='A'):
            subprocess.call(["omxplayer", "--no-osd", "warning1.mp3"])

    else:
        if(lcdDisplay==True):
            lcd.displayText("cfont1.ttf", fontSize=24, text=msgReceived, position=(lcd_Line2Pixel(0), 10) )

        logger.info('Unknow ID: ' + msgReceived)

def on_publish(mosq, obj, mid):
    if(debugPrint==True): print("mid: " + str(mid))

def on_subscribe(mosq, obj, mid, granted_qos):
    if(debugPrint==True): print("Subscribed: " + str(mid) + " " + str(granted_qos))
    logger.info("MQTT subscribed: " + str(mid) + " " + str(granted_qos))

def on_log(mosq, obj, level, string):
    if(debugPrint==True): print(string)

mqttc = mqtt.Client()

# Assign event callbacks
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

# Connect
mqttc.username_pw_set(MQTTuser, MQTTpwd)
mqttc.connect(MQTTaddress, MQTTport, MQTTtimeout)

#while True:
#    print(time.time()-lastTimeRead)
#    if((time.time()-lastTimeRead)>screenSaverDelay and screenSaverNow==False):
#        print("Display screen saveer.")
#        logger.info("Display screen saveer.")
#        lcd.displayImg("rfidbg.jpg")
#        screenSaverNow = True

# Continue the network loop
mqttc.loop_forever()
