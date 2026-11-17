
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


class KvaserCanSender:

    def __init__(self, root):
        self.root = root
        self.root.title("Kvaser CAN FD Wakeup PDU Sender")
        self.root.geometry("950x700")

        self.bus = None
        self.periodic_running = False
        self.periodic_thread = None

        self.create_gui()

    def create_gui(self):

        # ---------------------------------
        # CAN Interface Configuration
        # ---------------------------------

        connection = ttk.LabelFrame(
            self.root,
            text="CAN Interface Configuration"
        )
        connection.pack(fill="x", padx=10, pady=10)

        ttk.Label(
            connection, text="Interface:"
        ).grid(row=0, column=0, padx=5, pady=8)

        ttk.Label(
            connection,
            text="Kvaser USBcan Pro 2xHS v2"
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(
            connection, text="CAN Channel:"
        ).grid(row=0, column=2, padx=5, pady=8, sticky="e")

        self.channel = ttk.Combobox(
            connection,
            values=["0", "1"],
            state="readonly",
            width=8
        )
        self.channel.set("0")
        self.channel.grid(row=0, column=3, padx=5, sticky="w")

        ttk.Label(
            connection, text="Nominal Bitrate:"
        ).grid(row=1, column=0, padx=5, pady=8)

        self.bitrate = ttk.Combobox(
            connection,
            values=[
                "125000",
                "250000",
                "500000",
                "800000",
                "1000000"
            ],
            state="readonly",
            width=15
        )
        self.bitrate.set("500000")
        self.bitrate.grid(row=1, column=1, sticky="w")

        ttk.Label(
            connection, text="Data Bitrate:"
        ).grid(row=2, column=0, padx=5, pady=8)

        self.data_bitrate = ttk.Combobox(
            connection,
            values=[
                "1000000",
                "2000000",
                "4000000",
                "5000000"
            ],
            state="readonly",
            width=15
        )
        self.data_bitrate.set("2000000")
        self.data_bitrate.grid(row=2, column=1, sticky="w")

        self.can_fd = tk.BooleanVar(value=True)

        self.can_fd_check = ttk.Checkbutton(
            connection,
            text="Enable CAN FD",
            variable=self.can_fd
        )
        self.can_fd_check.grid(row=2, column=2, padx=10)

        self.connect_button = ttk.Button(
            connection,
            text="Connect",
            command=self.connect
        )
        self.connect_button.grid(
            row=1, column=3, padx=10
        )

        self.disconnect_button = ttk.Button(
            connection,
            text="Disconnect",
            command=self.disconnect,
            state="disabled"
        )
        self.disconnect_button.grid(
            row=1, column=4, padx=5
        )

        self.status = ttk.Label(
            connection,
            text="Disconnected",
            foreground="red"
        )
        self.status.grid(
            row=3, column=1, sticky="w", pady=5
        )

        # ---------------------------------
        # CAN Message Configuration
        # ---------------------------------

        message_frame = ttk.LabelFrame(
            self.root,
            text="Wakeup CAN PDU Configuration"
        )
        message_frame.pack(
            fill="x", padx=10, pady=5
        )

        ttk.Label(
            message_frame,
            text="CAN ID (Hex):"
        ).grid(row=0, column=0, padx=5, pady=8)

        self.can_id = ttk.Entry(
            message_frame, width=25
        )
        self.can_id.insert(0, "1B000000")
        self.can_id.grid(row=0, column=1, padx=5)

        self.extended = tk.BooleanVar(value=True)

        ttk.Checkbutton(
            message_frame,
            text="Extended ID (29-bit)",
            variable=self.extended
        ).grid(row=0, column=2, padx=10)

        ttk.Label(
            message_frame,
            text="CAN Data (Hex):"
        ).grid(row=1, column=0, padx=5, pady=8)

        self.can_data = ttk.Entry(
            message_frame, width=75
        )

        self.can_data.insert(
            0,
            "40 FF FF FF FF FF FF FF "
            "00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00"
        )

        self.can_data.grid(
            row=1, column=1,
            columnspan=3, padx=5, sticky="w"
        )

        ttk.Label(
            message_frame,
            text="Payload length: 24 bytes"
        ).grid(
            row=2, column=1, sticky="w", padx=5
        )

        self.send_button = ttk.Button(
            message_frame,
            text="SEND CAN MESSAGE",
            command=self.send_message,
            state="disabled"
        )
        self.send_button.grid(
            row=3, column=1, padx=5, pady=15,
            sticky="w"
        )

        # ---------------------------------
        # Periodic Transmission
        # ---------------------------------

        periodic_frame = ttk.LabelFrame(
            self.root,
            text="Periodic CAN Transmission"
        )
        periodic_frame.pack(
            fill="x", padx=10, pady=5
        )

        ttk.Label(
            periodic_frame,
            text="Transmission Interval (ms):"
        ).grid(row=0, column=0, padx=5, pady=10)

        self.interval = ttk.Entry(
            periodic_frame, width=12
        )
        self.interval.insert(0, "100")
        self.interval.grid(row=0, column=1, padx=5)

        self.start_button = ttk.Button(
            periodic_frame,
            text="Start Periodic TX",
            command=self.start_periodic,
            state="disabled"
        )
        self.start_button.grid(
            row=0, column=2, padx=10
        )

        self.stop_button = ttk.Button(
            periodic_frame,
            text="Stop Periodic TX",
            command=self.stop_periodic,
            state="disabled"
        )
        self.stop_button.grid(
            row=0, column=3, padx=5
        )

        # ---------------------------------
        # Transmission Log
        # ---------------------------------

        log_frame = ttk.LabelFrame(
            self.root,
            text="CAN Transmission Log"
        )
        log_frame.pack(
            fill="both", expand=True,
            padx=10, pady=10
        )

        self.log = tk.Text(
            log_frame,
            height=15,
            width=100,
            state="disabled"
        )
        self.log.pack(
            fill="both", expand=True,
            padx=5, pady=5
        )

        ttk.Button(
            self.root,
            text="Clear Log",
            command=self.clear_log
        ).pack(pady=5)

    # ---------------------------------
    # Logging
    # ---------------------------------

    def write_log(self, text):

        timestamp = datetime.now().strftime(
            "%H:%M:%S.%f"
        )[:-3]

        def update():
            self.log.config(state="normal")
            self.log.insert(
                tk.END,
                f"[{timestamp}] {text}\n"
            )
            self.log.see(tk.END)
            self.log.config(state="disabled")

        self.root.after(0, update)

    # ---------------------------------
    # Connect Kvaser
    # ---------------------------------

    def connect(self):

        try:
            bitrate = int(self.bitrate.get())

            channel = int(self.channel.get())
            fd_enabled = self.can_fd.get()

            bus_config = {
                "interface": "kvaser",
                "channel": channel,
                "bitrate": bitrate,
            }

            if fd_enabled:
                data_bitrate = int(self.data_bitrate.get())
                bus_config["fd"] = True
                bus_config["data_bitrate"] = data_bitrate

            self.bus = can.Bus(**bus_config)

            mode_text = (
                f"Connected - CAN FD (data {data_bitrate} bps)"
                if fd_enabled else "Connected - Classic CAN"
            )
            self.status.config(
                text=f"{mode_text} - Channel {channel}",
                foreground="green"
            )

            self.connect_button.config(state="disabled")
            self.disconnect_button.config(state="normal")
            self.channel.config(state="disabled")
            self.bitrate.config(state="disabled")
            self.data_bitrate.config(state="disabled")
            self.can_fd_check.config(state="disabled")

            self.send_button.config(state="normal")
            self.start_button.config(state="normal")

            self.write_log(
                f"Kvaser USBcan Pro 2xHS v2 connected: "
                f"channel={channel}, nominal={bitrate} bps, "
                f"mode={'CAN FD' if fd_enabled else 'Classic CAN'}"
                + (f", data={data_bitrate} bps" if fd_enabled else "")
            )

        except Exception as e:

            self.bus = None

            messagebox.showerror(
                "Connection Error",
                str(e)
            )

    # ---------------------------------
    # Create CAN Message
    # ---------------------------------

    def get_message(self):

        try:

            can_id = int(
                self.can_id.get().strip(),
                16
            )

            if self.extended.get():

                if not 0 <= can_id <= 0x1FFFFFFF:
                    raise ValueError(
                        "Invalid 29-bit CAN ID"
                    )

            else:

                if not 0 <= can_id <= 0x7FF:
                    raise ValueError(
                        "Invalid 11-bit CAN ID"
                    )

            data_string = self.can_data.get().strip()

            data = bytes.fromhex(data_string)

            fd_enabled = self.can_fd.get()

            if fd_enabled:

                if len(data) > 64:
                    raise ValueError(
                        "CAN FD maximum payload is 64 bytes"
                    )

                valid_lengths = [
                    0, 1, 2, 3, 4, 5, 6, 7, 8,
                    12, 16, 20, 24, 32, 48, 64
                ]

                if len(data) not in valid_lengths:
                    raise ValueError(
                        "Invalid CAN FD payload length. "
                        "Use 0-8, 12, 16, 20, 24, 32, "
                        "48 or 64 bytes."
                    )

            else:

                if len(data) > 8:
                    raise ValueError(
                        "Classic CAN supports maximum 8 bytes"
                    )

            return can.Message(
                arbitration_id=can_id,
                data=data,
                is_extended_id=self.extended.get(),
                is_fd=fd_enabled,
                bitrate_switch=fd_enabled
            )

        except Exception as e:

            messagebox.showerror(
                "Invalid CAN Message",
                str(e)
            )

            return None

    # ---------------------------------
    # Manual Transmission
    # ---------------------------------

    def send_message(self):

        if not self.bus:
            return

        msg = self.get_message()

        if msg is None:
            return

        try:

            self.bus.send(msg, timeout=1.0)

            self.write_log(
                f"TX ID=0x{msg.arbitration_id:X} "
                f"Extended={msg.is_extended_id} "
                f"FD={msg.is_fd} "
                f"BRS={msg.bitrate_switch} "
                f"DLC={msg.dlc} "
                f"DATA={msg.data.hex(' ').upper()}"
            )

        except Exception as e:

            self.write_log(f"TX ERROR: {e}")

    # ---------------------------------
    # Start Periodic Transmission
    # ---------------------------------

    def start_periodic(self):

        if not self.bus or self.periodic_running:
            return

        try:

            interval = (
                float(self.interval.get()) / 1000
            )

            if interval <= 0:
                raise ValueError(
                    "Interval must be positive"
                )

        except ValueError as e:

            messagebox.showerror(
                "Invalid Interval",
                str(e)
            )
            return

        msg = self.get_message()

        if msg is None:
            return

        self.periodic_running = True

        self.start_button.config(
            state="disabled"
        )

        self.stop_button.config(
            state="normal"
        )

        self.periodic_thread = threading.Thread(
            target=self.periodic_transmit,
            args=(msg, interval),
            daemon=True
        )

        self.periodic_thread.start()

        self.write_log(
            f"Periodic TX started: "
            f"{interval * 1000:.1f} ms"
        )

    # ---------------------------------
    # Periodic TX Thread
    # ---------------------------------

    def periodic_transmit(self, msg, interval):

        next_tx = time.monotonic()

        while self.periodic_running:

            try:

                self.bus.send(msg, timeout=1.0)

                self.write_log(
                    f"TX ID=0x{msg.arbitration_id:X} "
                    f"FD={msg.is_fd} "
                    f"BRS={msg.bitrate_switch} "
                    f"DLC={msg.dlc} "
                    f"DATA={msg.data.hex(' ').upper()}"
                )

            except Exception as e:

                self.write_log(
                    f"TX ERROR: {e}"
                )
                break

            next_tx += interval

            time.sleep(
                max(
                    0,
                    next_tx - time.monotonic()
                )
            )

        self.root.after(
            0,
            self.periodic_finished
        )

    # ---------------------------------
    # Stop Periodic TX
    # ---------------------------------

    def stop_periodic(self):

        self.periodic_running = False

        self.write_log(
            "Periodic transmission stopped"
        )

    def periodic_finished(self):

        self.periodic_running = False

        self.start_button.config(
            state="normal" if self.bus else "disabled"
        )

        self.stop_button.config(
            state="disabled"
        )

    # ---------------------------------
    # Disconnect
    # ---------------------------------

    def disconnect(self):

        self.stop_periodic()

        if self.bus:

            try:
                self.bus.shutdown()

            except Exception as e:
                self.write_log(
                    f"Shutdown warning: {e}"
                )

            self.bus = None

        self.status.config(
            text="Disconnected",
            foreground="red"
        )

        self.connect_button.config(
            state="normal"
        )
        self.channel.config(state="readonly")
        self.bitrate.config(state="readonly")
        self.data_bitrate.config(state="readonly")
        self.can_fd_check.config(state="normal")

        self.disconnect_button.config(
            state="disabled"
        )

        self.send_button.config(
            state="disabled"
        )

        self.start_button.config(
            state="disabled"
        )

        self.stop_button.config(
            state="disabled"
        )

        self.write_log(
            "Kvaser disconnected"
        )

    # ---------------------------------
    # Clear Log
    # ---------------------------------

    def clear_log(self):

        self.log.config(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.config(state="disabled")

    # ---------------------------------
    # Application Close
    # ---------------------------------

    def close(self):

        self.periodic_running = False

        if self.bus:

            try:
                self.bus.shutdown()
            except Exception:
                pass

            self.bus = None

        self.root.destroy()


if __name__ == "__main__":

    root = tk.Tk()

    app = KvaserCanSender(root)

    root.protocol(
        "WM_DELETE_WINDOW",
        app.close
    )

    root.mainloop()
