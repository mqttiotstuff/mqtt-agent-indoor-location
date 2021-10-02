
#
# MQTT agent to manage indoor location
#
#


import paho.mqtt.client as mqtt
import random
import time
import re
import configparser
import os.path
import traceback


config = configparser.RawConfigParser()


deviceList = ["esp20","esp21","esp22"]
deviceLocation = {
        "esp20":"Bureau",
        "esp21":"Cuisine",
        "esp22":"Lampe"
        }
packet_topic_pattern = "home/{0}/sensors/packets" 
INDOOR = "home/agents/indoor"

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):

    global INDOOR
    global deviceList
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    for i in deviceList:
        subscribeTopic = packet_topic_pattern.format(i)
        print("subscribe to " + subscribeTopic)
        client.subscribe(subscribeTopic)

    for i in deviceList:
        subscribeTopic = "home/" + i + "/sensors/health"
        print("subscribed to healthcheck on " + subscribeTopic)
        client.subscribe(subscribeTopic)

# we have the address, and the mean, and the rssi
location = {}

knowndevices = ["feed5df56200", "2a:5b:e7:e8:42:6c"]
informations = { "98063ced6b53": "Montre Quentin",
        "feed5df56200": "Montre patrice"
        }

# 10 s for location information fadein, 
# windowed time
fadeintime = 10 

# last health check for the device
lasthealthCheck = {}
presence = {}

## remember the last relevant information for each sender
class EnqueuedPositions:

    def __init__(self):
        self.position = []

    def add(self, station, channel, rssi):
        timestamped = time.time()
        positiontuple = (timestamped, station, channel, rssi)
        self.position.append(positiontuple)
        # clean
        newarray = []
        for t in self.position:
            (timed, station, channel, rssi)  = t
            if timed + fadeintime > timestamped:
                # keep
                newarray.append(t)
        self.position = newarray

    def summarize(self):
        byStation = {}
        for t in self.position:
            (timed, station, channel, rssi)  = t
            byStation[station] = rssi
        return byStation

            
senderInformations = {}


topicre = re.compile("home/([^/]+)/sensors/packets")
wifi = re.compile("PACKET,CHAN=(\\d+),RS=([-]?\\d+),C=(\\d+),SNDR=(.*)$")
ble = re.compile("BLE,ADDR=([0-9a-f]+),RSSI=([-]?\\d+),ADVDATA=(.*)$")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
   global location
   try:

      # healthcheck ?
      if msg.topic[-len("health"):] == "health":
          e = msg.topic.split("/")[1]
          lasthealthCheck[e] = time.time()

      # evaluate device presence
      timeEvaluation = time.time()
      for i in lasthealthCheck:
          presence[i] = True
          if timeEvaluation - lasthealthCheck[i] > 3:
              presence[i] = False

      decoded_topic = topicre.match(msg.topic)
      if not decoded_topic:
          return

      station = decoded_topic.group(1)

      # get device, and associated
      packet = msg.payload.decode("utf-8")
      
    
      result = wifi.match(packet)
      current = {}
      sndr = None
      channel = None
      rssi = None
      if result:
          # print("match wifi " + str(result))
          
          rssi = int(result.group(2))/int(result.group(3))
          sndr = result.group(4)
          if sndr in location:
             current = location[sndr]
          
          channel = result.group(1)
          current[channel] = rssi

      else:

          rble = ble.match(packet)
          if rble:
              # print("match ble" + str(rble))
              channel = "ble"
              sndr = rble.group(1)
              rssi = int(rble.group(2))
              adv = rble.group(3)
              

              client2.publish(INDOOR + "/" + sndr + "/advertizing", str(adv))
              if sndr in informations:
                  client2.publish(INDOOR + "/" + sndr + "/informations", str(informations[sndr]))



      if (sndr is not None) and ((sndr in knowndevices) or channel == "ble") :
          c = EnqueuedPositions()
          if sndr in senderInformations:
              c = senderInformations[sndr]

          c.add(station, channel, rssi)
          senderInformations[sndr] = c
          s = c.summarize()
          s["presence"] = presence
          client2.publish(INDOOR + "/" + sndr + "/last10", str(s))

          client2.publish(INDOOR + "/" + sndr + "/" + station + "/" + channel, str(rssi))
          if station in deviceLocation:
              client2.publish(INDOOR + "/" + sndr + "/" + station, str(deviceLocation[station]))


   except Exception as e:
      traceback.print_exc()

   return


conffile = os.path.expanduser('~/.mqttagents.conf')
if not os.path.exists(conffile):
   raise Exception("config file " + conffile + " not found")

config.read(conffile)



username = config.get("agents","username")
password = config.get("agents","password")
mqttbroker = config.get("agents","mqttbroker")



client = mqtt.Client()
client2 = mqtt.Client()


client.on_connect = on_connect
client.on_message = on_message

client.username_pw_set(username, password)

# waiting for initial connection
while True:
   try:
      client.connect(mqttbroker, 1883, 60)
      break
   except:
      pass

print("connected")

# client2 is used to send time oriented messages, without blocking the receive one
client2.username_pw_set(username, password)
client2.connect(mqttbroker, 1883, 60)


# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.

client2.loop_start()
client.loop_start()


while True:
    try:
        time.sleep(2)
        client2.publish(INDOOR + "/healthcheck", "1")
    except KeyboardInterrupt:
        break;
    except:
        traceback.print_exc()








