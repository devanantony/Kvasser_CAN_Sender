# Kvasser CAN Sender

Python utilities for sending CAN and CAN FD frames through Kvaser interfaces.
The repository includes graphical desktop senders, Ubuntu SocketCAN integration,
command-line diagnostics, and a packaged Windows executable.

## Applications

| File | Platform | Purpose |
| --- | --- | --- |
| `kvaser_can_fd_sender.py` | Windows/Linux | Tkinter GUI for CAN FD or Classic CAN transmission on one selectable Kvaser channel. |
| `kvaser_can_sender.py` | Windows | Tkinter GUI for a Classic CAN-only Kvaser Leaf Light v2 connection on channel 0. |
| `kvaser_dual_channel_can_fd_sender.py` | Windows | Tkinter GUI for simultaneous CAN FD transmission on channels 0 and 1 of a USBcan Pro 2xHS v2. |
| `kvaser_universal_sender.py` | Windows/Linux | Auto-discovering multi-channel CAN workbench with independent and broadcast transmission. |
| `kvaser_universal_ubuntu.py` | Ubuntu/Linux | Ubuntu SocketCAN variant of the universal multi-channel workbench. |
| `kvasser.py` | Windows/Linux | Command-line probe for channel 0 that displays device information, bus state, and statistics. |
| `kvasse_diag.py` | Windows/Linux | Command-line diagnostic that sends ten standard 8-byte CAN frames on channel 0. |
| `kvaser_dual_channel_can_fd_sender.exe` | Windows | Packaged version of the dual-channel CAN FD sender. |

## Requirements

### Python

- Python 3
- Tkinter for the graphical applications
- `python-can`

Install the Python dependency:

```powershell
python -m pip install python-can
```

The GUI scripts use Tkinter, and the Kvaser scripts use `python-can`'s `kvaser`
interface. The Ubuntu script uses `python-can`'s `socketcan` interface.

### Hardware and drivers

For the Kvaser tools, install the Kvaser CANlib runtime/drivers and connect a
compatible Kvaser adapter. Bundled setup resources are under `drivers/`:

- `kvaser_drivers_setup-5.53.673.exe`
- `FwUpdateTool-4.42.0.zip`

For `kvaser_universal_ubuntu.py`, use Linux SocketCAN and configure the
detected Kvaser-backed interfaces before starting the application.

## Installation

Run commands from the repository directory.

### Windows

Install Python 3 and the Kvaser CANlib drivers, then install `python-can`:

```powershell
python -m pip install python-can
```

You can run a Python script:

```powershell
python kvaser_dual_channel_can_fd_sender.py
```

Or run the packaged executable:

```powershell
.\kvaser_dual_channel_can_fd_sender.exe
```

### Ubuntu

Install Python, Tkinter, `python-can`, and the SocketCAN utilities used by the
application:

```bash
sudo apt update
sudo apt install python3 python3-tk python3-pip can-utils
python3 -m pip install python-can
```

The Ubuntu workbench discovers available Kvaser-backed interfaces and uses
`pkexec` to configure them when it is not running as root.

## Usage

### Universal CAN workbench

```powershell
python kvaser_universal_sender.py
```

On Ubuntu, use the SocketCAN-specific variant:

```bash
python3 kvaser_universal_ubuntu.py
```

The universal workbench automatically discovers available CAN channels and
creates a control panel for each one. Use **Scan devices**, **Connect all**,
and **Disconnect all** to manage the detected channels. Each channel supports
Classic CAN or CAN FD bus mode, standard or extended identifiers, BRS, custom
payloads, one-shot transmission, and periodic transmission.

Additional controls include:

- **Wakeup preset** - loads the `0x1B000000` wakeup PDU configuration.
- **Broadcast source** - sends the selected source message to channels marked
  as broadcast targets.
- **Broadcast once** - sends one frame from the broadcast source.
- **Start broadcast** - starts periodic broadcast transmission.
- **Start selected independently** - starts periodic transmission using each
  target channel's own message settings.
- **Save settings** - saves channel settings in the user's home directory.
- **Stop all TX** - stops active transmission workers.
- **Device details** - displays detected devices and channel connection states.

On Windows, the universal sender discovers Kvaser channels through CANlib.
On Ubuntu, it discovers Kvaser-backed SocketCAN interfaces and can configure
them using `pkexec` when the application is not running as root.

### Single-channel CAN FD sender

```powershell
python kvaser_can_fd_sender.py
```

Select Kvaser channel 0 or 1, a nominal bitrate, and a data bitrate, then
connect. The nominal bitrate defaults to 500 kbit/s and the data bitrate
defaults to 2 Mbit/s. Channel, bitrate, and CAN FD settings are locked while
the bus is connected.

The window defaults to the wakeup PDU configuration:

- CAN FD enabled
- Extended ID `0x1B000000`
- 24-byte payload
- 100 ms periodic interval
- Bit-rate switching enabled for CAN FD frames

CAN IDs are entered in hexadecimal. Standard IDs must fit the 11-bit range
and extended IDs must fit the 29-bit range. Valid CAN FD payload lengths are
0-8, 12, 16, 20, 24, 32, 48, and 64 bytes. Disabling **Enable CAN FD** opens
a Classic CAN bus and restricts payloads to 8 bytes.

Use **SEND CAN MESSAGE** for a one-shot transmission, or enter a positive
interval in milliseconds and use **Start Periodic TX**. Periodic transmission
can be stopped from the same window. Transmission results and errors are
shown in the CAN transmission log.

### Classic CAN sender

```powershell
python kvaser_can_sender.py
```

This application opens Kvaser channel 0 and sends Classic CAN frames. Although
the UI contains a CAN FD checkbox and data bitrate selector, the Kvaser bus is
opened without CAN FD and created messages use `is_fd=False`. Payloads are
limited to 8 bytes even if the CAN FD checkbox is enabled.

### Dual-channel CAN FD sender

```powershell
python kvaser_dual_channel_can_fd_sender.py
```

The application opens both USBcan Pro 2xHS v2 channels using the same nominal
and data bitrates. Each channel has independent message settings and periodic
transmission. Broadcast mode sends the channel 0 message to both physical
channels and disables channel 1's message controls.

Use `Send on CH0` or `Send on CH1` for one-shot transmissions. In broadcast
mode, use channel 0's controls to send the shared message to both channels.

## Command-line diagnostics

List the channel 0 Kvaser connection, state, and statistics:

```powershell
python kvasser.py
```

Send ten standard 8-byte CAN frames with ID `0x123` and data
`11 22 33 44 55 66 77 88` at one-second intervals:

```powershell
python kvasse_diag.py
```

The diagnostic sends traffic on the CAN bus. Use it only when those frames and
the 500 kbit/s bitrate are appropriate for the connected network.

## Network safety

- CAN transmission requires correctly wired bus connections and compatible
  termination and bitrates.
- Ensure that the selected identifiers and payloads are acceptable for all
  devices on the network.
- Keep the CAN and CAN FD nominal/data bitrates consistent across the
  application and physical network.
- Stop periodic transmission and disconnect before closing the application.

## Repository resources

The repository also contains:

- `canlib/pycanlib-1.34.0.zip` - archived `pycanlib` package.
- `drivers/kvaser_drivers_setup-5.53.673.exe` - Kvaser CANlib driver setup.
- `drivers/FwUpdateTool-4.42.0.zip` - Kvaser firmware update tool archive.

## Troubleshooting

- **Connection failure:** verify that CANlib/SocketCAN is installed, the
  adapter or interface is available, and no other process is holding the
  channel.
- **Ubuntu interface is down:** configure it with `ip link` and set the CAN FD
  MTU to 72 bytes.
- **Ubuntu bitrate mismatch:** bring the interface down, configure the expected
  bitrates, and bring it back up.
- **Classic CAN payload rejected:** use no more than 8 bytes.
- **CAN FD payload rejected:** use a supported CAN FD DLC length.
- **No traffic observed:** verify the channel, CAN ID, bus termination,
  transceiver, wiring, and network bitrates.
