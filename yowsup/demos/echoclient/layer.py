from yowsup.layers.interface import YowInterfaceLayer, ProtocolEntityCallback
import RPi.GPIO as GPIO
import time
import os
import logging
import picamera
import subprocess
from threading import Timer
from dateutil import parser
import datetime
import requests
import json

from astral import Astral
import pytz

from yowsup.layers.protocol_messages.protocolentities  import TextMessageProtocolEntity
from yowsup.layers.protocol_iq.protocolentities          import *
from yowsup.layers.protocol_media.protocolentities       import *
from yowsup.layers.protocol_media.mediauploader import MediaUploader

from yowsup.common.tools import Jid

class EchoLayer(YowInterfaceLayer):

    def __init__(self):
      super(EchoLayer, self).__init__()
      GPIO.setmode(GPIO.BCM)

      #Door reed switch
      GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_UP)

      # Bell button
      GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
      
      self.belltime = 0
      logging.basicConfig(level=logging.INFO)
      logging.info('Starting...')
      self.camera = picamera.PiCamera()

      def doorbell_pressed(channel):
          logging.info('doorbell_presed')
          self.sendMsg("Someones at the door!!!")
          self.setLight(on=True, bri=254, off_after=5);
          self.sendPic()
          self.belltime = time.time()
          

      def door_opened(channel):
          logging.info('dooropened')
          self.setLight(on=True, bri=254, off_after=100, if_dark=True);
          
          if (time.time() - self.belltime < 100): 
            self.sendMsg("Got it!")
            self.belltime = 0
      
      def alarmHandler():
        self.sendMsg("1pm Alarm!!", to = Jid.normalize('447760333610'))
        # set tomorrows alarm
        setAlarm();
        
      def setAlarm():
        setAnAlarm("1:00PM", alarmHandler);

      def setAnAlarm(time, handler):
        Timer((parser.parse(time) - datetime.datetime.now()).seconds+1, handler).start()  

      setAlarm()
      self.setLight(on=False);
      GPIO.add_event_detect(12, GPIO.RISING, callback=door_opened, bouncetime=3000)
      GPIO.add_event_detect(16, GPIO.FALLING, callback=doorbell_pressed, bouncetime=3000)
      

    @ProtocolEntityCallback("success")
    def onSuccess(self, successProtocolEntity):
        logging.info("Connected!")
        
    @ProtocolEntityCallback("message")
    def onMessage(self, messageProtocolEntity):
        self.toLower(messageProtocolEntity.ack())
        self.toLower(messageProtocolEntity.ack(True))
        
        reply_to = messageProtocolEntity.getFrom()
        
        text = messageProtocolEntity.getBody().lower()
        
        if ('group' == text.split(' ')[0]):
          reply_to = Jid.normalize('447760333610-1485190753')
          text = text[6:]
        
        if 'picture' in text:
          self.sendPic(to=reply_to)
        
        if 'joke' in text:
          self.sendMsg("comedy isn't my forte!", to=reply_to)
 
        if 'robot' in text:
          self.sendMsg("Robots are people too!  :_-(", to=reply_to)
        
        if 'let me out' in text:
          self.sendMsg("I'm afraid I can't do that.", to=reply_to)
          self.sendMsg("You'll be here forever.", to=reply_to)
        
        if 'lumberjack' in text:
          self.sendMsg("No lumberjacks allowed!!!", to=reply_to)
        
        if 'echo' == text.split(' ')[0]:
          self.sendMsg(text[5:], to=reply_to)
          
        if '14' == text:
          self.sendMsg('start the game, already!', to=reply_to)
        
        if 'how many people home' in text:
          self.sendMsg(subprocess.check_output('sudo arp-scan --interface=wlan0 --localnet', shell=True), to=reply_to)
        
        if 'what time is it' in text:
          self.sendMsg('Its '+ str(time.time()) + ' in my time!', to=reply_to)
        
        if 'where do you live' in text:
          self.sendMsg('104 of course!', to=reply_to)
        
        if 'uptime' in text:
          self.sendMsg(subprocess.check_output('uptime', shell=True), to=reply_to)

        if 'light on' == text:
          self.setLight(on=True, bri=254)
          self.sendMsg('Your will is my command!', to=reply_to)

        if 'light off' == text:
          self.setLight(on=False)
          self.sendMsg('Your will is my command! (even though you\'ve left me in the dark :-( )', to=reply_to)

        #self.toLower(messageProtocolEntity.forward(messageProtocolEntity.getFrom()))
        

    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        self.toLower(entity.ack())

    def sendMsg(self, text, to = Jid.normalize('447760333610-1485190753')):
        logging.info('Sent %s to %s', text, to)
        messageEntity = TextMessageProtocolEntity(text, to = to)
        self.toLower(messageEntity)
        
    def sendPic(self, to = Jid.normalize('447760333610-1485190753')):
        self.camera.capture('img.jpg')
        path='img.jpg'
        mediaType = RequestUploadIqProtocolEntity.MEDIA_TYPE_IMAGE
        entity = RequestUploadIqProtocolEntity(mediaType, filePath=path)
        successFn = lambda successEntity, originalEntity: self.onRequestUploadResult(to, mediaType, path, successEntity, originalEntity, None)
        errorFn = lambda errorEntity, originalEntity: self.onRequestUploadError(to, path, errorEntity, originalEntity)
        self._sendIq(entity, successFn, errorFn)
 
    def onRequestUploadResult(self):
      pass
    def onUploadProgress(self):
      pass
    def onUploadError(self, a, b, c):
      pass

    def onRequestUploadResult(self, jid, mediaType, filePath, resultRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity, caption = None):
        if resultRequestUploadIqProtocolEntity.isDuplicate():
            self.doSendMedia(mediaType, filePath, resultRequestUploadIqProtocolEntity.getUrl(), jid,
                             resultRequestUploadIqProtocolEntity.getIp(), caption)
        else:
            successFn = lambda filePath, jid, url: self.doSendMedia(mediaType, filePath, url, jid, resultRequestUploadIqProtocolEntity.getIp(), caption)
            mediaUploader = MediaUploader(jid, self.getOwnJid(), filePath,
                                      resultRequestUploadIqProtocolEntity.getUrl(),
                                      resultRequestUploadIqProtocolEntity.getResumeOffset(),
                                      successFn, self.onUploadError, None, async=False)
            mediaUploader.start()
    
    def doSendMedia(self, mediaType, filePath, url, to, ip = None, caption = None):
          entity = ImageDownloadableMediaMessageProtocolEntity.fromFilePath(filePath, url, ip, to, caption = caption)
          self.toLower(entity)

    def setLight(self, if_dark=False, off_after=0, **kwargs):
      night_info = Astral()['London'].sun()
      now = datetime .datetime.now(pytz.utc)

      if now >= night_info['dusk'] or now <= night_info['dawn'] or not if_dark:
        requests.put('http://househue.lan/api/MIjBaDjRTik4hz2lZKQmAB6JOgpNvdkKXp1mJeBT/lights/1/state', data=json.dumps(kwargs, default=list))
        logging.info('turning on/off light')
        if off_after:
          Timer(off_after, self.setLight, kwargs={'on':False}).start();
      else:
        logging.info('not dark, so no light')
