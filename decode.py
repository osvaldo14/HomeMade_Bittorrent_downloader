#!/usr/bin/env python
# -*- coding: utf-8 -*-

#Program for getting the two first pieces of a file using BitTorrent Protocol
 
#--------------- IMPORTATIONS -------------
from random import randint
from hashlib import sha1
from timeit import default_timer as timer

import bencode as bencode
import urllib2 as urllib2
import urllib  as urllib

import threading
import socket
import struct
import Queue
import time
import sys
import logging
import time

#------------- END IMPORTATIONS -----------

#------------- GLOBAL VARIABLES -----------

interval            = 0
info_hash           = 0
peer_id             = 0
reserved            = b"XXXXAAAA"

complete            = False
index               = 0
begin               = 0
block_length        = 1024
begin_timer         = 0

choked              = 1
interested          = 0
blocks              = []
blocks_received     = 0
pieces_received     = 0
piece_length        = 0                 # Taille en bytes de chaque pièce
peers_queue         = Queue.Queue()     # Queue qui contient les derniers peers collecté par THP
sha1_list           = []                # list of sha1 in torrent file


start               = 0
end                 = 0
peer_ipport         = ''
version_peer        = 'BitTorrent protocol/1.0'
pieces_list         = ''
speed               = 0
FORMAT              = '%(asctime)-15s %(peer_ipport)s %(version_peer)s %(speed)s Ko/s %(pieces_list)s'
logging.basicConfig(filename='infos.log', level=logging.INFO, format=FORMAT, filemode='w', datefmt='%m/%d/%Y %I:%M:%S %p')


#---------------- END VARIABLES ------------

#---------------- FUNCTIONS ----------------

'''
    Crée un port en concaténant 2 bytes
    Retourne un port (int)
'''
def createPort(string1, string2):
    return int(string1+string2, 2)

'''
    Crée un peer à partir d'un tableau de 6 bytes
    Retourne un peer (string) au format ip:port 
'''
def createPeer(byteList):
    port = createPort(byteList[4], byteList[5])
    return str(int(byteList[0], 2))+"."+str(int(byteList[1], 2))+"."+str(int(byteList[2], 2))+"."+str(int(byteList[3], 2))+":"+str(port)


def regroupList(lst, n):
    for i in range(0,len(lst), n):
        val = lst[i:i+n]
        if len(val) == n:
            yield tuple(val)

'''
    Essaie d'envoyer un message de handhsake à ip_port et attend sa réponse.
    Le handshake est réussi si les conditions suivantes sont validées: 
        - On a pu se connecter à ip_port en un temps inférieur à timeout
        - Le message de retour à notre handshake n'est pas vide ("")
    Retourne :
        - la socket connecté à ip_port, si le handhake a réussi
        - None autrement
'''
def handshake(ip_port, timeout=5):
    #handshake: <pstrlen><pstr><reserved><info_hash><peer_id>
    handshake_msg   = str(unichr(19))+b"BitTorrent protocol"+reserved+info_hash+peer_id
    ip, port        = ip_port.split(":")
    s               = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    s.settimeout(timeout)

    try:
        s.connect((ip, int(port)))
        s.send(handshake_msg)
        return_msg = s.recv(68)
        s.settimeout(None)
        if(len(return_msg) != 0):
            return s
        else:
            return None

    except Exception as e:
        #print e
        return None

'''
    Filtre les peers en gardant ceux dont on obtient une réponse non vide pour le handshake
    Retourne:   une queue`contenant des sockets vers les peers,
                "classés" du plus rapide au plus lent
'''
def get_peers_queue(peer_list):
    #-------------------------------------
    #Rajoute un peer à la queue si son handhsake est valide
    def add_peer_to_queue(ip_port, queue):
        socket = handshake(ip_port)
        if(socket):
            queue.put(socket)
    #-------------------------------------

    q       = Queue.Queue()
    threads = []

    for peer in peer_list:
        t = threading.Thread(target=add_peer_to_queue, args=(peer,q))
        t.daemon = True 
        threads.append(t)
    
    # Lancer tout les threads
    for t in threads:
        t.start()

    # Attendre la fin de tout les threads
    for t in threads:
        t.join()

    return q

#Réception du bitfield et retourne True si le bitfield est correcte
def get_bitfield(s,length):
    print("Bitfield :")
    bitfield = s.recv(length - 1)
    print(bitfield)
    if check_bitfield(length, bitfield):
        print("check ok !")
        return True
    else:
        print("check error !")
        return False



#Permet de vérifier si le bitfield est correcte
def check_bitfield(bitfield_size, bitfield):
    global pieces_list
    bitfield_stringified = ""
    for x in bitfield:
        for y in range(8):
            #ord(x) retourne la valeur numérique du caractère ascii
            bitfield_stringified += str(((ord(x)>>y)&1))
            pieces_list = bitfield_stringified

    return (len(bitfield_stringified)/8+1) == bitfield_size


#Envoi le message interested
def send_interested(socket):
    interested_msg = struct.pack('>IB', 1, 2)
    socket.send(interested_msg)


#Envoi le message uninterested
def send_uninterested(socket):
    uninterested_msg = struct.pack('>IB', 1, 3)
    socket.send(uninterested_msg)


#Envoi le message choke
def send_choke(socket):
    choke_msg = struct.pack('>IB', 1, 0)
    socket.send(choke_msg)

#Envoi le message permettant de demander des datas
def request_pieces(socket, index, begin, length):
    request_msg =struct.pack('>IBIII', 13, 6, index, begin, length)
    socket.send(request_msg)

#Traitement de la reception de data
def recv_block(socket, length):
    global start
    global index, begin, blocks, block_length, blocks_received, complete, piece_length
    
    index_recv = struct.unpack('>I',socket.recv(4))[0]
    begin_recv = struct.unpack('>I',socket.recv(4))[0]
    begin += block_length
    blocks_received += 1
    #print('recieving block : ', blocks_received)
    #if(index_recv==index and begin_recv==begin ): 
    #block = struct.unpack('>1024B',socket.recv(length-9))[0]
    block = socket.recv(length-9)
    #print(block)
    blocks.append(block)

    if (blocks_received < piece_length/block_length): 
        request_pieces(socket,index,begin,block_length)
        #else :
        #    print("Received wrong block : expected ", index, " (", begin, ") but received ", index_recv ," (", begin_recv, ")")
    else :
        print('piece complete')
        #block = socket.recv(length-9)
        complete = 1



#Fonction principale qui permet le traitement des messages reçus
def msg_reception(socket):
    global choked
    global interested
    global block_length
    global peer_ipport
    global start
    global begin_timer

    try:
        length = struct.unpack('>I',socket.recv(4))[0]
        #print("length : " , length)
    except struct.error:
        print('bad length : ')
        return -2

    try:
        msg_id = struct.unpack('>B',socket.recv(1))[0]
        #print("msg_id : " , msg_id)
    except struct.error:
        print('bad id')
        return -3

    if msg_id == 0:     #choke
        choked = 1
        print("You are choked...")

        return 0
    elif msg_id == 1:   #unchoke
        choked = 0
        start = time.time()
        begin_timer = begin
        index = pieces_list.index("1") # find the first available piece
        request_pieces(socket,index,begin,block_length)
        print("You are unchoked...")
        return 1
    elif msg_id == 2:   #interested 
        print("interested...") 
        send_choke(socket)      
        return 2
    elif msg_id == 3:   #uninterested  
        print("uninterested...")
        send_choke(socket)    
        return 3
    elif msg_id == 4:   #have
        print("have...")  
        socket.recv(4)
        send_choke(socket)      
        return 4
    elif msg_id == 5:   #bitfield
        if get_bitfield(socket,length):
            send_interested(socket)
            interested = 1
            peer_ipport = socket.getsockname()
        else :
            send_uninterested(socket)
            send_choke(socket)
        return 5
    elif msg_id == 6:   #request
        print("request...")  
        socket.recv(12)
        send_choke(socket)     
        return 6
    elif msg_id == 7:   #piece
        recv_block(socket,length)
        return 7
    elif msg_id == 8:   #cancel
        print("cancel...")
        socket.recv(12)
        send_choke(socket)      
        return 8
    elif msg_id == 9:   #port
        print("port...")
        socket.recv(2)     
        return 9
    else:               #invalid message
        return -1

#---------------- END FUNCTIONS ----------------


#***********************************************#
#***********************************************#
#              BIT TORRENT PROTOCOL             #
#***********************************************#
#***********************************************#

#-------------- GET TORRENT INFOS ---------------
# Open Torrent file
file    = open(str(sys.argv[1]), 'rb')
torrent = bencode.bdecode(file.read())
file.close()

'''  Print METAINFOS    '''
'''
    print "METAINFOS:\n"
    for k in torrent.keys():
        if(k != "info"):
            print k + "     : ", torrent[k]
        else:
            print k + " : "
            for key in torrent[k]:
                if (key != "pieces"):
                    print " " + key + "     :" , torrent[k][key]
'''

# Get global variables : sha1_list, piece_length, info_hash and peer_id
sha1_pieces     = torrent['info']['pieces']
sha1_list       = [sha1_pieces[k:k+20] for k in range(0, len(sha1_pieces), 20)]

piece_length    = torrent['info']['piece length']
info_hash       = sha1(bencode.bencode(torrent["info"])).digest()
peer_id         = sha1("LamaLamaLamaDuck").digest()

# Set variables for THP execution
tracker_url     = torrent["announce"]  # Sélection du tracker: Pour l'instant, et peut-être pour toujours, on prend simplement "announce"
request_params  = dict()

request_params["info_hash"]     = urllib.quote(info_hash)
request_params["peer_id"]       = urllib.quote(peer_id) #20-bytes quelconque
request_params["port"]          = "40959"
request_params["uploaded"]      = "0"
request_params["downloaded"]    = "0"
request_params["left"]          = "0"
request_params["event"]         = "started"
request_params["compact"]       = "1"
request_params["corrupt"]       = "0"
request_params["key"]           = "1D1573F1"
request_params["numwant"]       = "200"
request_params["no_peer_id"]    = "1"


#---------------- THP ----------------

# Mets à jour la queue des peers
def THP():

    global peers_queue, interval

    url_request	= tracker_url + "?" + "&".join(map(lambda x: x[0]+"="+x[1], request_params.items()))
    #print(url_request)

    # GET REQUEST
    request     = urllib2.Request(url_request)
    response    = bencode.bdecode(urllib2.urlopen(request).read())

    test        = response["peers"]
    interval    = response["interval"]
    bin_test    = ' '.join(format(ord(x), 'b') for x in test)
    test        = bin_test.split()
    tmp         = list(regroupList(test, 6))

    peerList    = map(lambda x: createPeer(x), tmp)

    peers_queue = get_peers_queue(peerList)

    if not complete:
        t = threading.Timer(interval, THP)
        t.daemon = True
        t.start()


THP()
request_params.pop("event")

#---------------- END THP ----------------



#---------------- PWP ----------------

#States :

socket = peers_queue.get()


while pieces_received < 2:

    while not complete:
        status = msg_reception(socket)
        if status > 0:
            pass
        elif status == 0: # choked
            end = time.time()
            speed = (begin - begin_timer) / (end - start)
            print('choked, changing peer...')
            d={'peer_ipport': peer_ipport,'version_peer':version_peer, 'speed' : int(speed/1024) ,'pieces_list' : pieces_list}
            logging.info('Needed infos',extra=d)
            #peers_queue = get_fastest_peer(peerList)
            socket = peers_queue.get()
        elif status == -1:
            print('bad message...')
            complete = 1;
        elif status == -2:
            print('bad -2...')
            complete = 1;
        elif status == -3:
            print('bad -3...')
            complete = 1;
        else:
            pass


    end = time.time()
    speed = (begin - begin_timer) / (end - start)
    print('choked, changing peer...')
    d={'peer_ipport': peer_ipport,'version_peer':version_peer, 'speed' : int(speed/1024) ,'pieces_list' : pieces_list}
    logging.info('Needed infos',extra=d)

    print("Sha1 de la pièce {} : ".format(index))
    print(sha1_pieces[20 * index : 20 + 20 * index])

    piece = "".join(str(block) for block in blocks)
    sha1_received_piece = sha1(piece).digest()
    print('Sha1 de la pièce reçue : ')
    print(sha1_received_piece)


    if(sha1_pieces[20 * index : 20 + 20 * index]==sha1_received_piece):
        print('Piece validated')
        success = True
    else:
        print('Wrong piece')
        success = False

    complete            = False
    index               = pieces_list.index("1", index+1) # find the next available piece
    begin               = 0
    blocks              = []
    blocks_received     = 0
    if success :
        pieces_received     += 1
    success = False

    start = time.time()
    begin_timer = begin
    request_pieces(socket,index,begin,block_length)
   

print('received 2 pieces, over and out')
#---------------- END PWP ----------------
