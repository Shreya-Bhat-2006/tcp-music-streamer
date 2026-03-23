import threading


class Buffer:

    def __init__(self, size=50):
        self.buffer = []
        self.size = size
        self.lock = threading.Lock()
        self.not_empty = threading.Event()

    def add_packet(self, packet):
        with self.lock:
            if len(self.buffer) < self.size:
                self.buffer.append(packet)
                self.not_empty.set()

    def get_packet(self, timeout=2):
        # Wait until there's something in the buffer
        self.not_empty.wait(timeout=timeout)
        with self.lock:
            if self.buffer:
                packet = self.buffer.pop(0)
                if not self.buffer:
                    self.not_empty.clear()
                return packet
        return None

    def is_empty(self):
        with self.lock:
            return len(self.buffer) == 0

    def fill_level(self):
        with self.lock:
            return len(self.buffer)
