import can
import time

CHANNEL = 0
BITRATE = 500000

bus = can.Bus(
    interface="kvaser",
    channel=CHANNEL,
    bitrate=BITRATE
)

print("\n=== KVASER DIAGNOSTIC ===")
print("Device:", bus.channel_info)
print("Initial state:", bus.state)

msg = can.Message(
    arbitration_id=0x123,
    data=[0x11, 0x22, 0x33, 0x44,
          0x55, 0x66, 0x77, 0x88],
    is_extended_id=False
)

for i in range(10):

    try:
        bus.send(msg, timeout=1.0)
        print(f"[{i+1}] TX completed")

    except can.CanError as e:
        print(f"[{i+1}] TX FAILED: {e}")

    print("Bus state:", bus.state)
    print("Statistics:", bus.get_stats())

    time.sleep(1)

bus.shutdown()

print("\nDiagnostic completed")
