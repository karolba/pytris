#!/usr/bin/env python3

import os
import sys
import threading
import paho.mqtt.client as mqtt

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    eprint("Connected with result code " + str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    if is_master:
        client.subscribe('game/%s/slave' % invite_code)
    else:
        client.subscribe('game/%s/master' % invite_code)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    sys.stdout.buffer.write(msg.payload)
    sys.stdout.flush()

def send_data(line):
    global client
    if is_master:
        client.publish('game/%s/master' % invite_code, payload=line)
    else:
        client.publish('game/%s/slave' % invite_code, payload=line)

def receiving_thread():
    client.loop_forever()

def main():
    global is_master, invite_code
    if sys.argv[1] == '--master':
        is_master = True
    elif sys.argv[1] == '--slave':
        is_master = False
    else:
        eprint("Wrong usage")
        return

    invite_code = sys.argv[2]

    global client, thr
    # orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    # fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("18.196.46.10", 1888, 5)

    thr = threading.Thread(target=receiving_thread, args=[])
    thr.start()

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        if line[0] == ord(b'\254'):
            pass
        send_data(line)
    client.loop_stop()

if __name__ == '__main__':
    main()