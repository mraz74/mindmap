import os
import time
import sys
import tkinter as tk
from tkinter import ttk
import winsound  # Windows only; modify for other OS


class NetworkMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Monitor")
        self.root.geometry("450x350")

        # Variables
        self.sound_enabled = tk.BooleanVar(value=True)
        self.beep_duration = tk.IntVar(value=10000)  # Default 10 seconds total
        self.running = False
        self.last_status = None

        # GUI Setup
        self.setup_gui()

        # Log file
        self.log_file = "network_log.txt"

        # Start monitoring
        self.start_monitoring()

    def setup_gui(self):
        # Status Label
        self.status_label = ttk.Label(self.root, text="Status: Initializing...")
        self.status_label.pack(pady=5)

        # Attempts Display
        self.attempts_text = tk.Text(self.root, height=5, width=50)
        self.attempts_text.pack(pady=5)

        # Log Display (status changes only)
        self.log_text = tk.Text(self.root, height=5, width=50)
        self.log_text.pack(pady=5)

        # Sound Checkbox
        self.sound_check = ttk.Checkbutton(
            self.root,
            text="Enable Sound Alerts",
            variable=self.sound_enabled
        )
        self.sound_check.pack(pady=5)

        # Total Beep Duration
        ttk.Label(self.root, text="Total Beep Duration (ms):").pack(pady=2)
        self.duration_entry = ttk.Entry(self.root, textvariable=self.beep_duration)
        self.duration_entry.pack(pady=2)

        # Start/Stop Button
        self.toggle_button = ttk.Button(
            self.root,
            text="Stop Monitoring",
            command=self.toggle_monitoring
        )
        self.toggle_button.pack(pady=5)

    def ping_website(self, url="google.com"):
        hostname = url.split('/')[0]
        if sys.platform == 'win32':
            response = os.system(f"ping -n 1 {hostname} > nul 2>&1")
        else:
            response = os.system(f"ping -c 1 {hostname} > /dev/null 2>&1")
        return response == 0

    def play_alternating_beep(self, total_duration):
        """Play alternating beeps for the total duration."""
        if not (self.sound_enabled.get() and sys.platform == 'win32'):
            return

        try:
            duration = max(100, min(total_duration, 10000))  # Limit 100ms-10s
            beep_length = 500  # 500ms per beep
            pause_length = 500  # 500ms pause between beeps
            cycles = duration // (beep_length + pause_length)  # Number of full cycles

            for _ in range(cycles):
                winsound.Beep(1000, beep_length)  # 1000 Hz for 500ms
                time.sleep(pause_length / 1000)  # Pause in seconds

            # Handle remaining time if duration isn't perfectly divisible
            remaining = duration % (beep_length + pause_length)
            if remaining > 0:
                winsound.Beep(1000, min(remaining, beep_length))
        except:
            pass  # Ignore invalid duration or sound errors

    def log_status(self, status):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Update attempts text every try
        attempt_msg = f"{timestamp} - Attempt: Network {'UP' if status else 'DOWN'}"
        self.attempts_text.insert(tk.END, attempt_msg + "\n")
        self.attempts_text.see(tk.END)

        # Update status label
        self.status_label.config(text=f"Status: {'UP' if status else 'DOWN'}")

        # Log only on status change
        if self.last_status is None or self.last_status != status:
            message = f"{timestamp} - Network {'UP' if status else 'DOWN'}"
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)

            # Write to file
            with open(self.log_file, 'a') as f:
                f.write(message + "\n")

            # Play alternating beep on status change
            self.play_alternating_beep(self.beep_duration.get())

        self.last_status = status

    def monitor(self):
        if not self.running:
            return

        status = self.ping_website()
        self.log_status(status)
        self.root.after(5000, self.monitor)  # Check every 5 seconds

    def start_monitoring(self):
        if not self.running:
            self.running = True
            self.toggle_button.config(text="Stop Monitoring")
            self.monitor()

    def stop_monitoring(self):
        self.running = False
        self.toggle_button.config(text="Start Monitoring")
        self.status_label.config(text="Status: Stopped")

    def toggle_monitoring(self):
        if self.running:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def on_closing(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = NetworkMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()