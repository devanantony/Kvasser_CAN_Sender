import can

bus = can.Bus(
    interface="kvaser",
    channel=0,
    bitrate=500000
)

print("Channel info:", bus.channel_info)

print("Bus state:", bus.state)

print("Bus statistics:", bus.get_stats())

bus.shutdown()