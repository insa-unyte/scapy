#!/usr/bin/python
import sys
import json
import argparse
import random as rd
from scapy.all import *


def error():
    print("ERROR : wrong arguments, acceptable values are :")
    print("---- IPV4  source (w.x.y.z)")
    print("---- IPV4  destination (w.x.y.z)")
    print("---- INT   source port (1000 < x < 10 000)")
    print("---- INT   destination port (1000 < y < 10 000, y != x)")
    print("---- INT   packet amount, (x > 0)")
    print("---- INT   MTU, (x > 18 if segmentation, x > 12 if single-packet message)")
    print("---- FLOAT sleep time in seconds, (x >= 0)")
    print("---- STR   message type, (x = ints or x = json)")
    print("---- FLOAT probability to drop a packet / segment")
    exit(0)
    return


udpnhl = 12  # udp-notif header length
ohl = 4  # option header length

nSenders = 4
mgids = []
for i in range(nSenders):
    mgids.append(2**((i) * 8) - 1)  # create an array of message generator ids
index = {}
for i in range(nSenders):
    # dictionary with key = message generator ids and values = message id increment
    index[mgids[i]] = 0


class UDPN(Packet):
    name = "UDPN"
    fields_desc = [BitField("ver", 0, 3),  # Version
                   BitField("spa", 0, 1),  # Space
                   BitField("eTyp", 1, 4),  # Encoding Type
                   BitField("hLen", udpnhl, 8),  # Header Length
                   BitField("mLen", udpnhl, 16),  # Message Length
                   BitField("msgGenID", 0, 32),  # Message-Generator-ID
                   BitField("msgID", 0, 32), ]  # Message ID


class OPT(Packet):
    name = "OPT"
    fields_desc = [BitField("type", 1, 8),  # Type
                   BitField("optlen", ohl, 8),  # Length
                   BitField("fraNum", 0, 15),  # Fragment Number
                   BitField("L", 0, 1), ]  # Last


class PAYLOAD(Packet):
    name = "PAYLOAD"
    fields_desc = [StrField("msg", "idle"), ]  # Notification Message


def generate(arguments):

    # Store all vars

    source = arguments.src_ip
    destination = arguments.dest_ip
    sourcePort = arguments.src_port
    destinationPort = arguments.dest_port
    nMessages = arguments.packet_amount
    mtu = arguments.mtu
    sleepTime = arguments.sleep_time
    payloadType = arguments.type
    packetLossProba = arguments.packet_loss_proba

    # MESSAGE GENERATION
    if str(payloadType) == "json":
        message = json.dumps(open("../message.json", 'r').read())
        message = json.loads(message)
    elif str(payloadType) == "ints":
        message = "0123456789"
        for n in range(10):
            message += message  # 2**10 times the integers string
    elif str(payloadType) == "rand":
        message = "0123456789"
        for m in range(rd.randint(6, 12)):
            message += message  # 2**randint(1,9) times the integers string
    else:
        error()

    maxl = mtu - udpnhl  # maximum UDP length minus header bytes
    for i in range(nMessages):

        # CHANGE MESSAGE IF GENERATION MUST BE RANDOM
        if str(payloadType) == "rand":
            message = "0123456789"
            for k in range(rd.randint(6, 12)):
                message += message

        if i != 0:
            time.sleep(sleepTime)
        sender = mgids[rd.randint(0, 3)]

        # CASE WITH SEGMENTATION
        if len(message) > maxl:
            maxl = mtu - udpnhl - ohl
            packet = IP(src=source, dst=destination) / \
                UDP()/UDPN()/OPT()/PAYLOAD()
            packet[PAYLOAD].msg = message
            msg = packet[PAYLOAD].msg
            nSegments = len(msg) // maxl
            if len(msg) % maxl != 0:
                # if the whole division has a remainder, there will be one more segment that will not be full (this is the general case of course)
                nSegments += 1
            for j in range(nSegments):
                segment = packet
                segment.sport = sourcePort
                segment.dport = destinationPort
                segment[UDPN].msgGenID = sender
                segment[UDPN].msgID = index[sender]
                segment[UDPN].hLen = udpnhl + ohl
                segment[OPT].fraNum = j
                # if the message string from maxl * j to its end is bigger than max packet size, it isn't the last one
                if (len(msg[maxl * j:]) > maxl):
                    # then evaluate a full message size in the string
                    segment[PAYLOAD].msg = msg[maxl * j:maxl * (j + 1)]
                    segment[UDPN].mLen = segment[UDPN].hLen + \
                        len(segment[PAYLOAD].msg)
                else:  # now it is the last one
                    # then evalutate whatever remains in the string, since it is equal to or lower than maxl * i
                    segment[PAYLOAD].msg = msg[maxl * j:]
                    segment[UDPN].mLen = segment[UDPN].hLen + \
                        len(segment[PAYLOAD].msg)
                    segment[OPT].L = 1  # change last value
                    # increment index after sending the last segment of message
                    index[sender] += 1

                # DISPLAY USEFUL INFORMATION
                # segment.show()
                # segment[UDPN].show()
                # segment[OPT].show()
                print("segment ", j, " hLen = ", segment[UDPN].hLen)
                print("segment ", j, " mLen = ", segment[UDPN].mLen)
                print("segment ", j, " msgGenID = ", segment[UDPN].msgGenID)
                print("segment ", j, " msgID ", segment[UDPN].msgID)
                print("segment ", j, " msg = ", segment[PAYLOAD].msg.decode())
                print("segment ", j, " type = ", segment[OPT].type)
                print("segment ", j, " fraNum = ", segment[OPT].fraNum)
                print("segment ", j, " optlen = ", segment[OPT].optlen)
                print("segment ", j, " L = ", segment[OPT].L)
                if float(packetLossProba) == 0:
                    send(segment)
                    wrpcap('filtered.pcap', segment, append=True)
                elif rd.randint(1, int(1 / float(packetLossProba))) != 1:
                    send(segment)
                    wrpcap('filtered.pcap', segment, append=True)
                else:
                    print("\n\n\nSEGMENT DROPPED\n\n\n")
        # CASE WITHOUT SEGMENTATION
        else:
            packet = IP(src=source, dst=destination)/UDP()/UDPN()/PAYLOAD()
            packet.sport = sourcePort
            packet.dport = destinationPort
            packet[PAYLOAD].msg = message
            packet[UDPN].mLen = packet[UDPN].hLen + len(packet[PAYLOAD].msg)
            packet[UDPN].msgGenID = sender
            packet[UDPN].msgID = index[sender]
            index[sender] += 1

            # DISPLAY USEFUL INFORMATION
            # packet.show()
            # packet[UDPN].show()
            print("packet mLen = ", packet[UDPN].mLen)
            print("packet msgGenID = ", packet[UDPN].msgGenID)
            print("packet msgID ", packet[UDPN].msgID)
            print("packet msg = ", packet[PAYLOAD].msg.decode())
            if float(packetLossProba) == 0:
                send(packet)
                wrpcap('filtered.pcap', packet, append=True)
            elif rd.randint(1, int(1 / float(packetLossProba))) != 1:
                send(packet)
                wrpcap('filtered.pcap', packet, append=True)
            else:
                print("\n\n\nPACKET DROPPED\n\n\n")
        print("Notification message ", str(i), " sent")
    return


if __name__ == "__main__":

    # argparse part and all it's components

    parser = argparse.ArgumentParser(
        description='Process scapy call arguments.')
    parser.add_argument('src_ip', metavar='src-ip', nargs=1,
                        help='w.x.y.z source IPv4 address.')
    parser.add_argument('dest_ip', metavar='dest-ip', nargs=1,
                        help='w.x.y.z dest IPv4 address.')
    parser.add_argument('src_port', metavar='src-port', nargs=1, type=int,
                        help='1000 < port < 10 000')
    parser.add_argument('dest_port', metavar='dest-port', nargs=1, type=int, help='1000 < port < 10 000')
    parser.add_argument('mtu', type=int, help='The packets MTU.')
    parser.add_argument('--packet-amount', '-n', type=int,
                        default=1, help='The number of packets to be sent')
    parser.add_argument('--sleep-time', '-s', type=float,
                        default=0.0, help='The sleep time between packets.')
    parser.add_argument('--type', '-t', default="ints",
                        choices=["ints", "json"], help='The type of data sent')
    parser.add_argument('--packet-loss-proba', '-l', type=int, default=0,
                        help='The probability of a packet loss during transmission')
    parser.add_argument('--verbose', '-v', type=int, default=0,
                        choices=[0, 1], help='The verbosity level of the program. Between 0 and 1')

    args = parser.parse_args()

    print("src", args.src_ip, args.src_port)
    print("dest", args.dest_ip, args.dest_port)
    print("mtu", args.mtu)
    print("packet loss", args.packet_loss_proba)

    generate(args)