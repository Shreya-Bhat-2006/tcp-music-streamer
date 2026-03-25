import threading   # Used for handling multiple threads safely


class Buffer:

    def __init__(self, size=50):
        # List to store incoming packets
        self.buffer = []

        # Maximum capacity of buffer
        self.size = size

        # Lock to prevent multiple threads accessing buffer at same time
        self.lock = threading.Lock()

        # Event to signal whether buffer has data or not
        # (acts like a flag: ON = not empty, OFF = empty)
        self.not_empty = threading.Event()

    def add_packet(self, packet):
        # Add a packet into buffer (called by receiving thread)
        
        # Lock ensures only one thread modifies buffer at a time
        with self.lock:
            
            # Check if buffer is not full
            if len(self.buffer) < self.size:
                
                # Add packet to buffer
                self.buffer.append(packet)
                
                # Signal that buffer now has data
                self.not_empty.set()

    def get_packet(self, timeout=2):
        # Get a packet from buffer (called by playback thread)

        # Wait until buffer has data (or timeout occurs)
        self.not_empty.wait(timeout=timeout)

        # Lock for safe access
        with self.lock:
            
            # Check if buffer has packets
            if self.buffer:
                
                # Remove first packet (FIFO: First In First Out)
                packet = self.buffer.pop(0)

                # If buffer becomes empty after removing packet
                if not self.buffer:
                    
                    # Clear event (signal buffer is empty now)
                    self.not_empty.clear()

                # Return the packet for playback
                return packet

        # If no packet available (timeout case)
        return None

    def is_empty(self):
        # Check whether buffer is empty
        
        # Lock for safe read
        with self.lock:
            return len(self.buffer) == 0  # True if empty, else False

    def fill_level(self):
        # Return number of packets currently in buffer
        
        # Lock for safe read
        with self.lock:
            return len(self.buffer)