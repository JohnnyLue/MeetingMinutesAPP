import socket
import cv2
import numpy as np
import logging
import argparse
import json

logger = logging.getLogger()
RETRY_TIMES = 10

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
        self.comm = None
        self._signal_func = {}
        self._require_data = {}
        
    def imServer(self):
        self.isClient = False
        self.isServer = True
        if self.conn is not None:
            self.conn.close()
            logger.info("Close previous connection")
        if self.inited:
            self.inited = False
            self.comm = None
            self.sock.close()
            logger.info("Close previous server")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        logger.info(f"Server listening on {self.host}:{self.port}")
        self.inited = True
        
        # Accepting connection
        conn, addr = self.sock.accept()
        logger.info(f"Server connect with {addr}")
        self.conn = conn
        self.comm = conn
    
    def imClient(self):
        self.isClient = True
        self.isServer = False
        if self.inited:
            self.inited = False
            self.comm = None
            self.sock.close()
            logger.info("Close previous client")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for _ in range(RETRY_TIMES):
            try:
                self.sock.connect((self.host, self.port))
                break
            except ConnectionRefusedError:
                logger.info(f"Failed to connect to {self.host}:{self.port}, try again.")
        logger.info(f"Client connected to {self.host}:{self.port}")
        self.inited = True
        self.comm = self.sock
                
    def send_signal(self, signal):
        if not self.inited:
            logger.warning("Not initialized")
            return
        if self.comm is None:
            logger.warning("No connection")
            return
        if not isinstance(signal, str) or signal.strip() == "":
            logger.warning("Invalid signal")
            return
        self.comm.sendall("SIG".encode())
        self.comm.sendall(signal.encode().ljust(30))
    
    def send_data(self, data):
        if not self.inited:
            logger.warning("Not initialized")
            return
        if self.comm is None:
            logger.warning("No connection")
            return
        if data is None:
            logger.warning("Invalid data")
            return
        self.comm.sendall("DAT".encode())
        json_data = json.dumps(data)
        data_len = len(json_data)
        self.comm.sendall(str(data_len).encode().ljust(16))
        self.comm.sendall(json_data.encode())
        
    def send_image(self, image):
        if not self.inited:
            logger.warning("Not initialized")
            return
        if self.comm is None:
            logger.warning("No connection")
            return
        if image is None:
            logger.warning("Invalid image")
            return
        self.comm.sendall("IMG".encode())
        _, image_data = cv2.imencode('.png', image)
        image_data = image_data.tobytes()
        data_len = len(image_data)
        self.comm.sendall(str(data_len).encode().ljust(16))
        self.comm.sendall(image_data)
        
    def receive(self):
        if not self.inited:
            logger.warning("Not initialized")
            return None, None
        if self.comm is None:
            logger.warning("No connection")
            return None, None
        
        type = self.comm.recv(3).decode()
        if type == "SIG":
            signal = self.comm.recv(30).decode() # Fixed max length of signal data
            signal = signal.strip()
            if not signal or not isinstance(signal, str):
                logger.warning("Failed signal receive")
                return None, None
            if signal in self._signal_func:
                if self._require_data[signal]:
                    type, data = self.receive()
                    if type != "DAT":
                        logger.warning("Expected data, not received")
                        return None, None
                    self._signal_func[signal](data)
                else:
                    self._signal_func[signal]()
            return type, signal
        elif type == "DAT":
            data_len = self.comm.recv(16).decode().strip() # Get the length of data
            if not data_len or int(data_len) <= 0:
                logger.warning("Failed data receive")
                return None, None
            data_len = int(data_len)
            data = b''
            while len(data) < data_len:
                package = self.comm.recv(min(data_len-len(data), self.buffer_size))
                if not package:
                    break
                data += package
            data = json.loads(data.decode()) 
            return type, data
        elif type == "IMG":
            data_len = self.comm.recv(16).decode().strip() # Get the length of data
            if not data_len or int(data_len) <= 0:
                logger.warning("Failed image receive")
                return None, None
            data_len = int(data_len)
            image_data = b''
            while len(image_data) < data_len:
                package = self.comm.recv(min(data_len-len(image_data), self.buffer_size))
                if not package:
                    break
                image_data += package
            image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
            return type, image
        else:
            logger.error("Unknown type of data")
            return None, None
        
    def connect_signal(self, signal, func, require_data = False):
        if not self.inited:
            logger.warning("Not initialized")
            return
        if self.comm is None:
            logger.warning("No connection")
            return
        if not isinstance(signal, str) or signal.strip() == "":
            logger.warning("Invalid signal")
            return
        if not callable(func):
            logger.warning("Invalid function")
            return
        
        self._signal_func[signal] = func
        self._require_data[signal] = require_data
        logger.debug(f"Connect signal: {signal}, function: {func.__name__}")
        
    def close(self):
        if self.isServer:
            self.conn.close()
            self.sock.close()
        elif self.isClient:
            self.sock.close()
        logger.info("Close connection")
        
    def __del__(self):
        self.close()
