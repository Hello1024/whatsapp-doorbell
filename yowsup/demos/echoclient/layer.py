from yowsup.layers.interface import YowInterfaceLayer, ProtocolEntityCallback
import RPi.GPIO as GPIO
import time
import os
import logging
import picamera
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
          self.sendPic()
          self.belltime = time.time()
          

      def door_opened(channel):
          logging.info('dooropened')
          if (time.time() - self.belltime < 100): 
            self.sendMsg("Got it!")
            self.belltime = 0

      GPIO.add_event_detect(12, GPIO.RISING, callback=door_opened, bouncetime=3000)
      GPIO.add_event_detect(16, GPIO.FALLING, callback=doorbell_pressed, bouncetime=3000)

    @ProtocolEntityCallback("success")
    def onSuccess(self, successProtocolEntity):
        logging.info("Connected!")
        
    @ProtocolEntityCallback("message")
    def onMessage(self, messageProtocolEntity):

        self.toLower(messageProtocolEntity.ack())
        self.toLower(messageProtocolEntity.ack(True))
        
        text = messageProtocolEntity.getBody().lower()
        if 'picture' in text:
          self.sendPic();
        
        if 'joke' in text:
          self.sendMsg("comedy isn't my forte!");
 
        if 'robot' in text:
          self.sendMsg("Robots are people too!  :_-(");
        
        if 'echo' == text.split(' ')[0]:
          self.sendMsg(messageProtocolEntity.getBody()[5:]);
        

        #self.toLower(messageProtocolEntity.forward(messageProtocolEntity.getFrom()))
        

    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        self.toLower(entity.ack())

    def sendMsg(self, text):
        logging.info('Sent %s', text)
        messageEntity = TextMessageProtocolEntity(text, to = Jid.normalize('447760333610-1485190753'))
        self.toLower(messageEntity)
        
    def sendPic(self):
          #os.system('raspistill -o img.jpg')
          self.camera.capture('img.jpg')
          path='img.jpg'
          jid=Jid.normalize('447760333610-1485190753')
          mediaType = RequestUploadIqProtocolEntity.MEDIA_TYPE_IMAGE
          entity = RequestUploadIqProtocolEntity(mediaType, filePath=path)
          successFn = lambda successEntity, originalEntity: self.onRequestUploadResult(jid, mediaType, path, successEntity, originalEntity, None)
          errorFn = lambda errorEntity, originalEntity: self.onRequestUploadError(jid, path, errorEntity, originalEntity)
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
