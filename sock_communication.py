import pickle
import struct

def send_msg(sock, data_to_pack):
    print(data_to_pack)
    data = pickle.dumps(data_to_pack)
    msg = struct.pack('>I', len(data)) + data
    #msg = pickle.dumps(len(data)) + data
    sock.sendall(msg)

def recv_msg(sock):
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        print("error")
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    #msglen = int(pickle.loads(raw_msglen))
    return recvall(sock, msglen)

def recvall(sock, n):
    '''recv n bytes or return None if EOF is hit'''
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data