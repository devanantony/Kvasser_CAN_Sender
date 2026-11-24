import tkinter as tk
from tkinter import ttk, messagebox
import can

# Explicit imports: PyInstaller may not detect python-can's dynamically
# loaded Kvaser backend when building the executable.
import can.interfaces.kvaser
import can.interfaces.kvaser.canlib

import threading
import time
from datetime import datetime


WAKEUP_ID = "1B000000"
WAKEUP_DATA = (
    "40 FF FF FF FF FF FF FF "
    "00 00 00 00 00 00 00 00 "
    "00 00 00 00 00 00 00 00"
)
WAKEUP_INTERVAL_MS = "100"


class ChannelConfig:
    def __init__(self, channel, parent):
        self.channel = channel
        self.bus = None
        self.running = False
        self.thread = None
        self.frame = ttk.LabelFrame(parent, text=f"CAN Channel {channel}")
        self.frame.pack(fill="x", padx=8, pady=6)

        self.preset = tk.StringVar(value="Custom")
        self.can_id = tk.StringVar(value=WAKEUP_ID)
        self.data = tk.StringVar(value=WAKEUP_DATA)
        self.extended = tk.BooleanVar(value=True)
        self.fd = tk.BooleanVar(value=True)
        self.brs = tk.BooleanVar(value=True)
        self.interval = tk.StringVar(value=WAKEUP_INTERVAL_MS)

        ttk.Label(self.frame, text="Message preset:").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.preset_box = ttk.Combobox(
            self.frame, textvariable=self.preset,
            values=["Custom", "Wakeup PDU (0x1B000000)"],
            state="readonly", width=27
        )
        self.preset_box.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.preset_box.bind("<<ComboboxSelected>>", self.apply_preset)

        ttk.Label(self.frame, text="CAN ID (hex):").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.id_entry = ttk.Entry(self.frame, textvariable=self.can_id, width=20)
        self.id_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.ext_check = ttk.Checkbutton(
            self.frame, text="Extended ID (29-bit)", variable=self.extended
        )
        self.ext_check.grid(row=1, column=2, padx=8, pady=5, sticky="w")

        ttk.Label(self.frame, text="Payload (hex bytes):").grid(
            row=2, column=0, padx=5, pady=5, sticky="w"
        )
        self.data_entry = ttk.Entry(
            self.frame, textvariable=self.data, width=100
        )
        self.data_entry.grid(
            row=2, column=1, columnspan=4, padx=5, pady=5, sticky="ew"
        )

        self.fd_check = ttk.Checkbutton(
            self.frame, text="CAN FD", variable=self.fd
        )
        self.fd_check.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.brs_check = ttk.Checkbutton(
            self.frame, text="Bit Rate Switching (BRS)", variable=self.brs
        )
        self.brs_check.grid(row=3, column=2, padx=5, pady=5, sticky="w")

        ttk.Label(self.frame, text="Periodic interval (ms):").grid(
            row=3, column=3, padx=5, pady=5, sticky="e"
        )
        self.interval_entry = ttk.Entry(
            self.frame, textvariable=self.interval, width=10
        )
        self.interval_entry.grid(row=3, column=4, padx=5, pady=5, sticky="w")

        self.send_button = ttk.Button(
            self.frame, text=f"Send on CH{channel}",
            command=lambda: None, state="disabled"
        )
        self.send_button.grid(row=4, column=1, padx=5, pady=8, sticky="w")

        self.start_button = ttk.Button(
            self.frame, text="Start periodic",
            command=lambda: None, state="disabled"
        )
        self.start_button.grid(row=4, column=2, padx=5, pady=8, sticky="w")

        self.stop_button = ttk.Button(
            self.frame, text="Stop periodic",
            command=lambda: None, state="disabled"
        )
        self.stop_button.grid(row=4, column=3, padx=5, pady=8, sticky="w")

        self.frame.columnconfigure(1, weight=1)

    def apply_preset(self, _event=None):
        if self.preset.get().startswith("Wakeup PDU"):
            self.can_id.set(WAKEUP_ID)
            self.data.set(WAKEUP_DATA)
            self.extended.set(True)
            self.fd.set(True)
            self.brs.set(True)
            self.interval.set(WAKEUP_INTERVAL_MS)


class KvaserDualChannelSender:
    def __init__(self, root):
        self.root = root
        self.root.title("Kvaser USBcan Pro 2xHS v2 - Dual Channel CAN FD Sender")
        self.root.geometry("1120x900")
        self.root.minsize(950, 760)

        self.connected = False
        self.broadcast_same = tk.BooleanVar(value=False)
        self.channel_cfg = {}

        self.create_gui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def create_gui(self):
        connection = ttk.LabelFrame(
            self.root, text="Kvaser USBcan Pro 2xHS v2 - Interface Configuration"
        )
        connection.pack(fill="x", padx=10, pady=8)

        ttk.Label(connection, text="Nominal bitrate:").grid(
            row=0, column=0, padx=5, pady=6, sticky="w"
        )
        self.nominal_bitrate = ttk.Combobox(
            connection,
            values=["125000", "250000", "500000", "800000", "1000000"],
            state="readonly", width=13
        )
        self.nominal_bitrate.set("500000")
        self.nominal_bitrate.grid(row=0, column=1, padx=5, pady=6)

        ttk.Label(connection, text="Data bitrate:").grid(
            row=0, column=2, padx=5, pady=6, sticky="w"
        )
        self.data_bitrate = ttk.Combobox(
            connection,
            values=["1000000", "2000000", "4000000", "5000000"],
            state="readonly", width=13
        )
        self.data_bitrate.set("2000000")
        self.data_bitrate.grid(row=0, column=3, padx=5, pady=6)

        self.connect_button = ttk.Button(
            connection, text="Connect BOTH channels", command=self.connect
        )
        self.connect_button.grid(row=0, column=4, padx=10, pady=6)

        self.disconnect_button = ttk.Button(
            connection, text="Disconnect BOTH", command=self.disconnect,
            state="disabled"
        )
        self.disconnect_button.grid(row=0, column=5, padx=5, pady=6)

        self.status = ttk.Label(
            connection, text="Disconnected", foreground="red"
        )
        self.status.grid(row=1, column=0, columnspan=6, padx=5, pady=5, sticky="w")

        broadcast = ttk.LabelFrame(self.root, text="Transmission Mode")
        broadcast.pack(fill="x", padx=10, pady=5)
        self.broadcast_check = ttk.Checkbutton(
            broadcast,
            text="Send the SAME CAN-FD message configured in Channel 0 to BOTH channels",
            variable=self.broadcast_same,
            command=self.broadcast_changed
        )
        self.broadcast_check.pack(anchor="w", padx=8, pady=6)

        self.channel_container = ttk.Frame(self.root)
        self.channel_container.pack(fill="x", padx=4, pady=2)

        for ch in (0, 1):
            cfg = ChannelConfig(ch, self.channel_container)
            self.channel_cfg[ch] = cfg
            cfg.send_button.configure(command=lambda c=ch: self.send_message(c))
            cfg.start_button.configure(command=lambda c=ch: self.start_periodic(c))
            cfg.stop_button.configure(command=lambda c=ch: self.stop_periodic(c))

        log_frame = ttk.LabelFrame(self.root, text="CAN Transmission Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=8)
        self.log = tk.Text(log_frame, height=12, width=120, state="disabled")
        self.log.pack(fill="both", expand=True, padx=5, pady=5)

        ttk.Button(self.root, text="Clear Log", command=self.clear_log).pack(pady=4)

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        def update():
            self.log.configure(state="normal")
            self.log.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log.see(tk.END)
            self.log.configure(state="disabled")

        self.root.after(0, update)

    def connect(self):
        opened = []
        try:
            nominal = int(self.nominal_bitrate.get())
            data_rate = int(self.data_bitrate.get())

            # Open each physical Kvaser channel as its own python-can Bus.
            # Keeping both Bus objects open allows independent simultaneous TX.
            for ch in (0, 1):
                bus = can.Bus(
                    interface="kvaser",
                    channel=ch,
                    bitrate=nominal,
                    fd=True,
                    data_bitrate=data_rate
                )
                self.channel_cfg[ch].bus = bus
                opened.append(bus)

            self.connected = True
            self.connect_button.configure(state="disabled")
            self.disconnect_button.configure(state="normal")
            self.nominal_bitrate.configure(state="disabled")
            self.data_bitrate.configure(state="disabled")

            for ch in (0, 1):
                cfg = self.channel_cfg[ch]
                cfg.send_button.configure(state="normal")
                cfg.start_button.configure(state="normal")

            self.status.configure(
                text=f"Connected: CH0 + CH1 | Nominal {nominal} bps | "
                    f"Data {data_rate} bps | CAN FD",
                foreground="green"
            )
            self.log_message(
                f"Kvaser USBcan Pro 2xHS v2 connected on both channels "
                f"(nominal={nominal}, data={data_rate}, CAN FD)"
            )
            self.broadcast_changed()

        except Exception as exc:
            for bus in opened:
                try:
                    bus.shutdown()
                except Exception:
                    pass
            for cfg in self.channel_cfg.values():
                cfg.bus = None
            self.connected = False
            messagebox.showerror(
                "Kvaser connection error",
                "Could not open both CAN channels.\n\n"
                f"{exc}\n\n"
                "Check that the Kvaser CANlib driver is installed and that "
                "both channels are available."
            )

    def broadcast_changed(self):
        cfg1 = self.channel_cfg.get(1)
        if cfg1 is None:
            return
        if self.broadcast_same.get():
            # Channel 0 is the source message in broadcast mode.
            state = "disabled"
            cfg1.preset_box.configure(state="disabled")
            cfg1.id_entry.configure(state="disabled")
            cfg1.data_entry.configure(state="disabled")
            cfg1.ext_check.configure(state="disabled")
            cfg1.fd_check.configure(state="disabled")
            cfg1.brs_check.configure(state="disabled")
            cfg1.interval_entry.configure(state="disabled")
            cfg1.start_button.configure(state="disabled")
            cfg1.send_button.configure(
                state="normal" if self.connected else "disabled"
            )
            self.log_message(
                "Broadcast enabled: Channel 0 message will be sent on CH0 and CH1"
            )
        else:
            cfg1.preset_box.configure(state="readonly")
            cfg1.id_entry.configure(state="normal")
            cfg1.data_entry.configure(state="normal")
            cfg1.ext_check.configure(state="normal")
            cfg1.fd_check.configure(state="normal")
            cfg1.brs_check.configure(state="normal")
            cfg1.interval_entry.configure(state="normal")
            cfg1.send_button.configure(
                state="normal" if self.connected else "disabled"
            )
            cfg1.start_button.configure(
                state="normal" if self.connected else "disabled"
            )
            self.log_message("Broadcast disabled: CH0 and CH1 use separate messages")

    def build_message(self, ch):
        cfg = self.channel_cfg[ch]
        can_id = int(cfg.can_id.get().strip().replace("0x", "").replace("0X", ""), 16)
        is_extended = cfg.extended.get()
        if is_extended and not 0 <= can_id <= 0x1FFFFFFF:
            raise ValueError(f"CH{ch}: CAN ID is outside the 29-bit range")
        if not is_extended and not 0 <= can_id <= 0x7FF:
            raise ValueError(f"CH{ch}: CAN ID is outside the 11-bit range")

        data = bytes.fromhex(cfg.data.get().strip())
        fd = cfg.fd.get()
        brs = cfg.brs.get() if fd else False

        if fd:
            valid_lengths = {0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64}
            if len(data) not in valid_lengths:
                raise ValueError(
                    f"CH{ch}: Invalid CAN FD payload length ({len(data)} bytes). "
                    "Allowed lengths: 0-8, 12, 16, 20, 24, 32, 48, 64."
                )
        elif len(data) > 8:
            raise ValueError(f"CH{ch}: Classic CAN payload cannot exceed 8 bytes")

        return can.Message(
            arbitration_id=can_id,
            data=data,
            is_extended_id=is_extended,
            is_fd=fd,
            bitrate_switch=brs
        )

    def targets_for(self, requested_channel):
        if self.broadcast_same.get():
            return [0, 1]
        return [requested_channel]

    def transmit_one(self, ch, msg):
        """Transmit on one CAN channel without waiting for the other channel."""
        bus = self.channel_cfg[ch].bus
        if bus is None:
            self.log_message(f"TX ERROR CH{ch}: channel is not connected")
            return
        try:
            bus.send(msg, timeout=1.0)
            self.log_message(
                f"TX CH{ch}: ID=0x{msg.arbitration_id:X} "
                f"Extended={msg.is_extended_id} FD={msg.is_fd} "
                f"BRS={msg.bitrate_switch} DLC={msg.dlc} "
                f"DATA={msg.data.hex(' ').upper()}"
            )
        except Exception as exc:
            self.log_message(f"TX ERROR CH{ch}: {type(exc).__name__}: {exc}")

    def transmit(self, requested_channel, msg):
        """Launch a separate one-shot TX task for each target channel."""
        for ch in self.targets_for(requested_channel):
            threading.Thread(
                target=self.transmit_one, args=(ch, msg), daemon=True
            ).start()

    def send_message(self, requested_channel):
        if not self.connected:
            return
        try:
            source_channel = 0 if self.broadcast_same.get() else requested_channel
            msg = self.build_message(source_channel)
            self.transmit(requested_channel, msg)
        except Exception as exc:
            messagebox.showerror("CAN transmission error", str(exc))

    def start_periodic(self, requested_channel):
        if not self.connected:
            return

        targets = self.targets_for(requested_channel)
        if any(self.channel_cfg[ch].running for ch in targets):
            return

        source_channel = 0 if self.broadcast_same.get() else requested_channel
        source_cfg = self.channel_cfg[source_channel]
        try:
            interval = float(source_cfg.interval.get()) / 1000.0
            if interval <= 0:
                raise ValueError("Interval must be greater than zero")
            msg = self.build_message(source_channel)
        except Exception as exc:
            messagebox.showerror("Periodic TX configuration error", str(exc))
            return

        # Each physical channel has its own scheduler and TX worker.
        for ch in targets:
            cfg = self.channel_cfg[ch]
            cfg.running = True
            cfg.thread = threading.Thread(
                target=self.periodic_worker,
                args=(ch, msg, interval),
                daemon=True
            )
            cfg.thread.start()

        if self.broadcast_same.get():
            self.channel_cfg[0].start_button.configure(state="disabled")
            self.channel_cfg[0].stop_button.configure(state="normal")
            self.channel_cfg[1].start_button.configure(state="disabled")
            self.channel_cfg[1].stop_button.configure(state="disabled")
            self.log_message(
                f"Parallel broadcast started: CH0 and CH1 independently, "
                f"period={interval * 1000:.1f} ms"
            )
        else:
            cfg = self.channel_cfg[requested_channel]
            cfg.start_button.configure(state="disabled")
            cfg.stop_button.configure(state="normal")
            self.log_message(
                f"Periodic TX started on CH{requested_channel}: "
                f"{interval * 1000:.1f} ms"
            )

    def periodic_worker(self, ch, msg, interval):
        cfg = self.channel_cfg[ch]
        next_tx = time.monotonic()
        while cfg.running:
            try:
                # This worker sends only through its own channel handle.
                cfg.bus.send(msg, timeout=1.0)
                self.log_message(
                    f"TX CH{ch}: ID=0x{msg.arbitration_id:X} "
                    f"Extended={msg.is_extended_id} FD={msg.is_fd} "
                    f"BRS={msg.bitrate_switch} DLC={msg.dlc} "
                    f"DATA={msg.data.hex(' ').upper()}"
                )
            except Exception as exc:
                cfg.running = False
                self.log_message(
                    f"TX ERROR CH{ch}: {type(exc).__name__}: {exc}. "
                    f"Stopped periodic TX on CH{ch} only."
                )
                break

            next_tx += interval
            time.sleep(max(0, next_tx - time.monotonic()))

        self.root.after(0, lambda c=ch: self.periodic_finished(c))

    def stop_periodic(self, ch):
        if self.broadcast_same.get() and ch == 0:
            for channel in (0, 1):
                self.channel_cfg[channel].running = False
            self.log_message("Stop requested for broadcast on CH0 and CH1")
        else:
            self.channel_cfg[ch].running = False
            self.log_message(f"Periodic TX stop requested for CH{ch}")
        self.channel_cfg[ch].stop_button.configure(state="disabled")

    def periodic_finished(self, ch):
        cfg = self.channel_cfg[ch]
        cfg.running = False

        if self.broadcast_same.get():
            any_running = any(self.channel_cfg[c].running for c in (0, 1))
            self.channel_cfg[0].start_button.configure(
                state="disabled" if any_running or not self.connected else "normal"
            )
            self.channel_cfg[0].stop_button.configure(
                state="normal" if any_running else "disabled"
            )
            self.channel_cfg[1].start_button.configure(state="disabled")
            self.channel_cfg[1].stop_button.configure(state="disabled")
            if not any_running:
                self.log_message("Both-channel periodic broadcast has stopped")
        else:
            cfg.stop_button.configure(state="disabled")
            cfg.start_button.configure(
                state="normal" if self.connected else "disabled"
            )

    def disconnect(self):
        for cfg in self.channel_cfg.values():
            cfg.running = False

        for ch, cfg in self.channel_cfg.items():
            if cfg.bus is not None:
                try:
                    cfg.bus.shutdown()
                except Exception as exc:
                    self.log_message(f"CH{ch} shutdown warning: {exc}")
                cfg.bus = None

        self.connected = False
        self.connect_button.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self.nominal_bitrate.configure(state="readonly")
        self.data_bitrate.configure(state="readonly")
        self.status.configure(text="Disconnected", foreground="red")

        for ch, cfg in self.channel_cfg.items():
            cfg.send_button.configure(state="disabled")
            cfg.start_button.configure(state="disabled")
            cfg.stop_button.configure(state="disabled")

        self.log_message("Both Kvaser channels disconnected")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")

    def close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = KvaserDualChannelSender(root)
    root.mainloop()
