# Kvasser CAN Sender

Small Python utilities for sending CAN and CAN FD frames through Kvaser
interfaces. The repository contains three graphical senders and two
command-line diagnostics.

## Files

| File | Purpose |
| --- | --- |
| `kvaser_can_fd_sender.py` | Tkinter GUI for one selectable channel (0 or 1) on a Kvaser USBcan Pro 2xHS v2. Supports Classic CAN or CAN FD, manual or periodic transmission, and a transmission log. |
| `kvaser_can_sender.py` | Tkinter GUI for Classic CAN on channel 0. Provides manual and periodic transmission and a log. The CAN FD checkbox only changes the payload-length check; frames are still created as Classic CAN. Its default 24-byte payload therefore cannot be sent as a Classic CAN frame. |
| `kvaser_dual_channel_can_fd_sender.py` | Tkinter GUI that opens channels 0 and 1 of a Kvaser USBcan Pro 2xHS v2, with separate message settings or an option to broadcast the channel 0 message to both channels. Supports manual and periodic CAN FD transmission. |
| `kvasser.py` | Short command-line probe that opens channel 0 at 500 kbit/s and prints channel information, bus state, and statistics. It does not transmit a frame. |
| `kvasse_diag.py` | Command-line transmission diagnostic for channel 0 at 500 kbit/s. Sends ten standard 8-byte CAN frames with ID `0x123`, one per second, and reports transmission results, bus state, and statistics. |

## Requirements

- Python 3 with Tkinter available (required for the graphical senders).
- The `python-can` package.
- Kvaser CANlib drivers/runtime and a compatible Kvaser adapter for hardware use.

The repository does not include a dependency manifest or pin package versions.
Install `python-can` in the Python environment you intend to use:

```powershell
python -m pip install python-can
```

Install the Kvaser CANlib software separately using Kvaser's distribution for
your operating system and adapter. The scripts use `python-can`'s `kvaser`
interface; a connected, available channel is needed to open a bus.

## Run

Run commands from the repository directory:

```powershell
python kvaser_can_fd_sender.py
python kvaser_can_sender.py
python kvaser_dual_channel_can_fd_sender.py
python kvasser.py
python kvasse_diag.py
```

The first three commands open a Tkinter window. The last two run in the
terminal and close the CAN bus when complete.

## Graphical senders

### Single-channel CAN FD sender

`kvaser_can_fd_sender.py` defaults to channel 0, nominal bitrate 500 kbit/s,
data bitrate 2 Mbit/s, CAN FD enabled, and extended ID `0x1B000000`. Its
default wakeup payload is 24 bytes and its periodic interval is 100 ms.

Choose channel 0 or 1 and the nominal/data bitrates before connecting. When
connected, the interface settings are locked until disconnect. CAN IDs are
entered in hexadecimal. The GUI validates standard 11-bit or extended 29-bit
IDs and checks Classic CAN/FD payload length. CAN FD payloads must be 0–8,
12, 16, 20, 24, 32, 48, or 64 bytes. CAN FD frames use bitrate switching (BRS).
Use **SEND CAN MESSAGE** for a single frame, or set a positive interval in
milliseconds and start periodic transmission. The log shows transmitted
frames and transmission errors.

### Classic CAN sender

`kvaser_can_sender.py` opens channel 0 at the selected nominal bitrate
(default 500 kbit/s). Although its window includes a CAN FD checkbox and a
data bitrate selector, the connection is opened without CAN FD and the
created frames are Classic CAN. The checkbox changes the payload-length
validation only; Classic CAN frames are limited to 8 bytes. The GUI's default
payload is 24 bytes, so replace it with a Classic CAN-sized payload before
sending.

### Dual-channel CAN FD sender

`kvaser_dual_channel_can_fd_sender.py` opens channels 0 and 1 with the same
nominal and data bitrates (defaults 500 kbit/s and 2 Mbit/s). Configure the
message and periodic interval for each channel independently, or enable
broadcast mode to send the channel 0 message to both channels. In broadcast
mode, channel 1's message settings are disabled and its periodic start button
is unavailable. Each channel supports manual and periodic transmission.

Both CAN FD-capable senders default to the wakeup PDU configuration: extended
ID `0x1B000000`, a 24-byte payload, CAN FD enabled, and a 100 ms periodic
interval. In the dual-channel sender, BRS can be toggled per channel; in the
single-channel sender, BRS is enabled whenever CAN FD is enabled.

## Command-line diagnostics

`kvasser.py` is a read-only connectivity/state check after bus initialization:
it prints channel information, bus state, and statistics, then shuts down.

`kvasse_diag.py` is not read-only. It transmits ten standard CAN frames
(ID `0x123`, data `11 22 33 44 55 66 77 88`) at one-second intervals on
channel 0, printing transmission status, bus state, and statistics after each
attempt. Use it only when transmitting these frames on the connected CAN bus
is appropriate.

## Notes

- The applications are configured for Kvaser hardware and do not provide
  automatic adapter discovery.
- CAN transmission requires a correctly configured CAN network, including
  compatible bitrates and physical-layer setup. Check the adapter, driver,
  channel availability, and bus wiring if a connection or transmission fails.
- The scripts report connection and transmission errors in a dialog or log,
  depending on the application.
