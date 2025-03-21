import os
import time
import sys
import tkinter as tk
from tkinter import ttk
import winsound  # Windows only; modify for other OS

# Configuration Variables
CHECK_INTERVAL_MS = 5000  # Time between checks in milliseconds
DEFAULT_BEEP_DURATION_MS = 5000  # Default total beep duration in milliseconds (5 seconds)
WINDOW_SIZE = "450x370"  # Window dimensions (width x height)
LOG_FILE_PATH = "network_log.txt"  # Path to the log file
PING_URL = "google.com"  # URL to ping
BEEP_FREQUENCY_HZ = 500  # Beep frequency in Hertz
BEEP_LENGTH_MS = 400  # Duration of each individual beep in milliseconds
PAUSE_LENGTH_MS = 600  # Pause duration between beeps in milliseconds
MIN_BEEP_DURATION_MS = 100  # Minimum allowed beep duration
MAX_BEEP_DURATION_MS = 10000  # Maximum allowed beep duration

class NetworkMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Monitor")
        self.root.geometry(WINDOW_SIZE)

        # Variables
        self.sound_enabled = tk.BooleanVar(value=True)
        self.beep_duration = tk.IntVar(value=DEFAULT_BEEP_DURATION_MS)
        self.running = False
        self.last_status = None
        self.start_time = None
        self.first_status_set = False  # Track if first status has been set

        # GUI Setup
        self.setup_gui()

        # Log file
        self.log_file = LOG_FILE_PATH

        # Initial beep when program starts
        if sys.platform == 'win32':
            winsound.Beep(BEEP_FREQUENCY_HZ, BEEP_LENGTH_MS)

        # Start monitoring
        self.start_monitoring()

    def setup_gui(self):
        self.start_time_label = ttk.Label(self.root, text="Start Time: Not started")
        self.start_time_label.pack(pady=5)

        self.status_label = ttk.Label(self.root, text="Status: Initializing...")
        self.status_label.pack(pady=5)

        self.attempts_text = tk.Text(self.root, height=5, width=50)
        self.attempts_text.pack(pady=5)

        self.log_text = tk.Text(self.root, height=5, width=50)
        self.log_text.pack(pady=5)

        self.sound_check = ttk.Checkbutton(
            self.root,
            text="Enable Sound Alerts",
            variable=self.sound_enabled
        )
        self.sound_check.pack(pady=5)

        ttk.Label(self.root, text="Total Beep Duration (ms):").pack(pady=2)
        self.duration_entry = ttk.Entry(self.root, textvariable=self.beep_duration)
        self.duration_entry.pack(pady=2)

        self.toggle_button = ttk.Button(
            self.root,
            text="Stop Monitoring",
            command=self.toggle_monitoring
        )
        self.toggle_button.pack(pady=5)

    def ping_website(self, url=PING_URL):
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
            duration = max(MIN_BEEP_DURATION_MS, min(total_duration, MAX_BEEP_DURATION_MS))
            cycles = duration // (BEEP_LENGTH_MS + PAUSE_LENGTH_MS)

            for _ in range(cycles):
                winsound.Beep(BEEP_FREQUENCY_HZ, BEEP_LENGTH_MS)
                time.sleep(PAUSE_LENGTH_MS / 1000)

            remaining = duration % (BEEP_LENGTH_MS + PAUSE_LENGTH_MS)
            if remaining > 0:
                winsound.Beep(BEEP_FREQUENCY_HZ, min(remaining, BEEP_LENGTH_MS))
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

            with open(self.log_file, 'a') as f:
                f.write(message + "\n")

            # Beep only after first status change
            if self.first_status_set:
                self.play_alternating_beep(self.beep_duration.get())

        self.last_status = status
        self.first_status_set = True  # Mark first status as set after first check

    def monitor(self):
        if not self.running:
            return

        status = self.ping_website()
        self.log_status(status)
        self.root.after(CHECK_INTERVAL_MS, self.monitor)

    def start_monitoring(self):
        if not self.running:
            self.running = True
            self.toggle_button.config(text="Stop Monitoring")
            self.start_time = time.strftime("%Y-%m-%d %H:%M:%S")
            self.start_time_label.config(text=f"Start Time: {self.start_time}")
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