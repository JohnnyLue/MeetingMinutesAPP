import socket
import cv2
import numpy as np
import logging
import argparse
import json

logger = logging.getLogger(__name__)

class SocketInterface():
    def __init__(self, host='localhost', port=8080, buffer_size=1024):
        self.sock = None
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.conn = None
        self.inited = False
        self.isServer = False
        self.isClient = False
        
    def imServer(self):
        self.isClient = False
        self.isServer = True
        if self.inited:
            self.inited = False
            self.sock.close()
            logger.info("Close previous server")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        logger.info(f"Server listening on {self.host}:{self.port}")
        self.inited = True        
        
    def accept_connection(self):
        if not self.isServer:
            logger.error("Not a server")
            return
        if self.conn is not None:
            self.conn.close()
            logger.info("Close previous connection")
        conn, addr = self.sock.accept()
        logger.info(f"Server connect with {addr}")
        self.conn = conn
        return conn, addr
    
    def imClient(self):
        self.isClient = True
        self.isServer = False
        if self.inited:
            self.inited = False
            self.sock.close()
            logger.info("Close previous client")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        logger.info(f"Client connected to {self.host}:{self.port}")
        self.inited = True
                
    def send_signal(self, signal):
        self.sock.sendall("SIG".encode())
        self.sock.sendall(f"{signal}".encode())
    
    def send_data(self, data):
        self.sock.sendall("DAT".encode())
        json_data = json.dumps(data)
        data_len = len(json_data)
        self.sock.sendall(str(data_len).encode().ljust(16))
        self.sock.sendall(json_data.encode())
        
    def send_image(self, image):
        self.sock.sendall("IMG".encode())
        _, image_data = cv2.imencode('.png', image)
        image_data = image_data.tobytes()
        data_len = len(image_data)
        self.sock.sendall(str(data_len).encode().ljust(16))
        self.sock.sendall(image_data)
        
    def receive(self):
        tag = self.conn.recv(3).decode()
        if tag == "SIG":
            signal = self.conn.recv(self.buffer_size).decode()
            return signal
        elif tag == "DAT":
            data_len = self.conn.recv(16).decode().strip() # Get the length of data
            if not data_len or int(data_len) <= 0:
                logger.error("Data length is invalid")
                return None
            data_len = int(data_len)
            data = b''
            while len(data) < data_len:
                package = self.conn.recv(min(data_len-len(data), self.buffer_size))
                if not package:
                    break
                data += package
            data = json.loads(data.decode()) 
            return data
        elif tag == "IMG":
            data_len = self.conn.recv(16).decode().strip() # Get the length of data
            if not data_len or int(data_len) <= 0:
                logger.error("Data length is invalid")
                return None
            data_len = int(data_len)
            image_data = b''
            while len(image_data) < data_len:
                package = self.conn.recv(min(data_len-len(image_data), self.buffer_size))
                if not package:
                    break
                image_data += package
            image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
            return image
        else:
            logger.error("Unknown type of data")
        logger.debug(f"Received: {tag}")
        
if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--host", type=str, default="localhost")
    argparser.add_argument("--port", type=int, default=8080)
    argparser.add_argument("--buffer_size", type=int, default=1024)
    argparser.add_argument("--isServer", action="store_true")
    args = argparser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    if args.isServer:
        si = SocketInterface()
        si.imServer()
        si.accept_connection()
        recv = si.receive()
        logger.debug(f"Received: {recv}")
        recv = si.receive()
        logger.debug(f"Received: {recv}")
        recv = si.receive()
        cv2.imshow("Received", recv)
        cv2.waitKey(0)
    else:
        si = SocketInterface()
        si.imClient()
        logger.debug(f"Sending: Hello")
        si.send_signal("Hello")
        a = list(range(10))
        logger.debug(f"Sending: {a}")
        si.send_data(a)
        logger.debug(f"Sending: Image")
        img = cv2.imread("Darkeum.png")
        cv2.imshow("Image", img)
        si.send_image(img)
        cv2.waitKey(0)
        