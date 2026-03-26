import time


class QoS:

    def __init__(self):
        self.start_time = time.time()
        self.packets_received = 0
        self.packets_lost = 0
        self.latencies = []

    def packet_received(self, latency=None):
        self.packets_received += 1
        if latency is not None:
            self.latencies.append(latency)

    def packet_lost(self):
        self.packets_lost += 1

    def get_report(self):
        duration = time.time() - self.start_time
        total = self.packets_received + self.packets_lost
        loss_pct = (self.packets_lost / total * 100) if total > 0 else 0  # packet loss % — shows how many packets were lost during streaming
        avg_latency = (sum(self.latencies) / len(self.latencies) * 1000) if self.latencies else 0  # average time taken for each packet to travel from server to client

        return (
            f"Packets received : {self.packets_received}\n"
            f"Packets lost     : {self.packets_lost}\n"
            f"Packet loss      : {loss_pct:.2f}%\n"
            f"Avg latency      : {avg_latency:.2f} ms\n"
            f"Streaming time   : {round(duration, 2)} seconds"
        )

    def report(self):
        print("\n------ QoS Report ------")
        print(self.get_report())
