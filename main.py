import gc
import json
import math
import os
import select
import socket
import time

import machine
import network

# ==========================================
# HTML INTERFACE (Embedded - 100% Offline)
# ==========================================
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Biomechanics Logger</title>
    <style>
        :root {
            --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8;
            --primary: #2563eb; --primary-hover: #1d4ed8;
            --danger: #ef4444; --danger-hover: #dc2626;
            --success: #10b981; --success-hover: #059669;
            --border: #334155; --accent: #60a5fa;
            --warning: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, sans-serif; user-select: none; }
        body { background-color: var(--bg); color: var(--text); touch-action: manipulation; display: flex; flex-direction: column; height: 100vh; width: 100vw; align-items: center; justify-content: center; padding: 20px; }
        
        .container { max-width: 400px; width: 100%; text-align: center; display: flex; flex-direction: column; gap: 20px; }
        .card { background-color: var(--card); padding: 24px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid var(--border); }
        h1 { color: var(--accent); font-size: 2rem; margin-bottom: 10px; }
        p { color: var(--muted); text-align: center; margin-bottom: 10px; }
        
        button { width: 100%; color: white; border: none; padding: 18px 30px; border-radius: 50px; font-size: 1.2rem; font-weight: bold; cursor: pointer; transition: transform 0.1s; margin-top: 10px; }
        button:active { transform: scale(0.96); }
        button:disabled { opacity: 0.5; pointer-events: none; }
        
        .btn-start { background-color: var(--success); }
        .btn-stop { background-color: var(--danger); }
        .btn-download { background-color: var(--primary); }
        
        .status-bar { position: absolute; top: 15px; width: 100%; padding: 0 15px; display: flex; justify-content: space-between; align-items: flex-start; z-index: 100; pointer-events: none; }
        .right-badges { display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
        .badge-ui { background: rgba(0,0,0,0.5); padding: 5px 12px; border-radius: 20px; font-size: 0.9rem; font-weight: bold; border: 1px solid var(--border); box-shadow: 0 2px 10px rgba(0,0,0,0.5); }
        
        .wifi-status { color: #4ade80; }
        .bat-status { color: var(--accent); }
        .storage-status { color: var(--accent); }
        
        .status-indicator { margin-top: 10px; font-size: 1.2rem; font-weight: bold; color: var(--muted); }
        .time-indicator { margin-top: 5px; font-size: 0.9rem; color: var(--accent); margin-bottom: 15px; }
        .recording-pulse { color: var(--danger); animation: pulse 1.5s infinite; }
        
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="status-bar">
        <div id="wifi-status" class="badge-ui wifi-status">🟢 Connected</div>
        <div class="right-badges">
            <div id="bat-status" class="badge-ui bat-status">🔋 --%</div>
            <div id="storage-status" class="badge-ui storage-status">💾 --%</div>
        </div>
    </div>

    <div class="container">
        <div class="card">
            <h1>Run Biomechanics</h1>
            <p>Place device in central back pocket. (Logs at ~100Hz)</p>
            
            <div id="status-text" class="status-indicator">Status: Idle</div>
            <div id="time-recorded-text" class="time-indicator">Time Recorded: 0m 0s</div>
            
            <button id="btn-start" class="btn-start" onclick="startRecording()">START RECORDING</button>
            <button id="btn-stop" class="btn-stop" onclick="stopRecording()" style="display: none;">STOP RECORDING</button>
            <button id="btn-download" class="btn-download" onclick="downloadData()" disabled>DOWNLOAD CSV</button>
        </div>
    </div>

    <script>
        let isRecording = false;
        let hasData = false;
        let isCountingDown = false;
        const wifiStatus = document.getElementById('wifi-status');
        const batStatus = document.getElementById('bat-status');
        const storageStatus = document.getElementById('storage-status');
        const timeRecordedText = document.getElementById('time-recorded-text');

        function formatTime(seconds) {
            let h = Math.floor(seconds / 3600);
            let m = Math.floor((seconds % 3600) / 60);
            let s = seconds % 60;
            if (h > 0) return `${h}h ${m}m ${s}s`;
            return `${m}m ${s}s`;
        }

        function updateConnectionState(isOnline) {
            if (isOnline) {
                if (wifiStatus.innerText !== '🟢 Connected') {
                    wifiStatus.innerText = '🟢 Connected';
                    wifiStatus.style.color = '#4ade80';
                }
            } else {
                if (wifiStatus.innerText !== '🔴 Offline') {
                    wifiStatus.innerText = '🔴 Offline';
                    wifiStatus.style.color = '#ef4444';
                }
            }
        }

        async function updateStatus() {
            if (isCountingDown) return; 
            
            try {
                let res = await fetch('/status', { signal: AbortSignal.timeout(2000) });
                if (!res.ok) throw new Error("Network error");
                updateConnectionState(true);
                let data = await res.json();
                
                isRecording = data.recording;
                hasData = data.has_data;
                
                // Update Battery
                batStatus.innerText = `🔋 ${data.bat}%`;
                if (data.bat <= 20) batStatus.style.color = "#ef4444";
                else batStatus.style.color = "var(--accent)";
                
                // Update Storage Percentage
                storageStatus.innerText = `💾 ${data.storage_pct}%`;
                if (data.storage_pct <= 10) storageStatus.style.color = "#ef4444";
                else storageStatus.style.color = "var(--accent)";
                
                // Update Time Recorded
                timeRecordedText.innerText = `Time Recorded: ${formatTime(data.elapsed_time)}`;
                if (isRecording) timeRecordedText.style.color = "var(--danger)";
                else timeRecordedText.style.color = "var(--accent)";
                
                let btnStart = document.getElementById('btn-start');
                let btnStop = document.getElementById('btn-stop');
                let btnDownload = document.getElementById('btn-download');

                if (isRecording) {
                    btnStart.style.display = 'none';
                    btnStart.innerText = 'START RECORDING';
                    btnStart.disabled = false;
                    
                    btnStop.style.display = 'block';
                    if (btnStop.innerText !== 'STOPPING...') {
                        btnStop.disabled = false;
                        btnStop.innerText = 'STOP RECORDING';
                    }
                    btnDownload.disabled = true;
                    document.getElementById('status-text').innerHTML = 'Status: <span class="recording-pulse">RECORDING...</span>';
                } else {
                    btnStart.style.display = 'block';
                    btnStart.disabled = false;
                    btnStart.innerText = 'START RECORDING';
                    
                    btnStop.style.display = 'none';
                    btnStop.innerText = 'STOP RECORDING';
                    btnStop.disabled = false;
                    
                    btnDownload.disabled = !hasData;
                    document.getElementById('status-text').innerHTML = 'Status: Idle';
                }
            } catch (e) {
                updateConnectionState(false);
            }
        }

        async function startRecording() {
            if (hasData) {
                if (!confirm("Starting a new recording will overwrite the existing data. Continue?")) {
                    return;
                }
            }
            
            isCountingDown = true;
            let btnStart = document.getElementById('btn-start');
            btnStart.disabled = true;
            
            timeRecordedText.innerText = "Time Recorded: 0m 0s";
            
            for(let i = 3; i > 0; i--) {
                btnStart.innerText = i + "...";
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            btnStart.innerText = "GO!";
            await new Promise(resolve => setTimeout(resolve, 500));
            
            try {
                await fetch('/start');
            } catch (e) {
                console.error(e);
            }
            isCountingDown = false;
            updateStatus();
        }

        async function stopRecording() {
            let btnStop = document.getElementById('btn-stop');
            btnStop.disabled = true;
            btnStop.innerText = 'STOPPING...';
            
            try {
                await fetch('/stop');
            } catch (e) {
                console.error(e);
            }
            updateStatus();
        }

        function downloadData() {
            window.location.href = '/download';
        }

        setInterval(updateStatus, 1000); // Updated to 1000ms so the timer updates every second
        updateStatus();
    </script>
</body>
</html>"""

# ==========================================
# BATTERY MONITOR
# ==========================================
class StickPlus2Battery:
    def __init__(self):
        self.adc = machine.ADC(machine.Pin(38))
        self.adc.atten(machine.ADC.ATTN_11DB)
        self.adc.width(machine.ADC.WIDTH_12BIT)

    def get_battery_level(self):
        try:
            raw = self.adc.read()
            pct = ((raw - 1900) / 700.0) * 100
            return max(0, min(100, int(pct)))
        except Exception:
            return 100

# ==========================================
# MPU6886 FULL 6-AXIS DRIVER
# ==========================================
class MPU6886:
    def __init__(self, i2c):
        self.i2c = i2c
        self.addr = 0x68
        self.alpha = 0.3
        self.f_ax, self.f_ay, self.f_az = 0.0, 0.0, 1.0
        self.f_gx, self.f_gy, self.f_gz = 0.0, 0.0, 0.0
        self.sensor_data = [0.0] * 6

        try:
            self.i2c.writeto_mem(self.addr, 0x6B, b"\x00")
            time.sleep_ms(10)
            self.i2c.writeto_mem(self.addr, 0x1C, b"\x10")
            self.i2c.writeto_mem(self.addr, 0x1B, b"\x18")
            self.connected = True
        except OSError:
            self.connected = False

    def get_data(self):
        if not self.connected:
            return self.sensor_data
        try:
            data = self.i2c.readfrom_mem(self.addr, 0x3B, 14)
            def to_signed(msb, lsb):
                val = (msb << 8) | lsb
                return val if val < 32768 else val - 65536

            raw_ax = to_signed(data[0], data[1]) / 4096.0
            raw_ay = to_signed(data[2], data[3]) / 4096.0
            raw_az = to_signed(data[4], data[5]) / 4096.0
            raw_gx = to_signed(data[8], data[9]) / 16.4
            raw_gy = to_signed(data[10], data[11]) / 16.4
            raw_gz = to_signed(data[12], data[13]) / 16.4

            self.f_ax = (self.alpha * raw_ax) + ((1.0 - self.alpha) * self.f_ax)
            self.f_ay = (self.alpha * raw_ay) + ((1.0 - self.alpha) * self.f_ay)
            self.f_az = (self.alpha * raw_az) + ((1.0 - self.alpha) * self.f_az)
            self.f_gx = (self.alpha * raw_gx) + ((1.0 - self.alpha) * self.f_gx)
            self.f_gy = (self.alpha * raw_gy) + ((1.0 - self.alpha) * self.f_gy)
            self.f_gz = (self.alpha * raw_gz) + ((1.0 - self.alpha) * self.f_gz)

            self.sensor_data[0] = self.f_ax
            self.sensor_data[1] = self.f_ay
            self.sensor_data[2] = self.f_az
            self.sensor_data[3] = self.f_gx
            self.sensor_data[4] = self.f_gy
            self.sensor_data[5] = self.f_gz
            return self.sensor_data
        except OSError:
            return self.sensor_data

# ==========================================
# EDGE COMPUTING - DATA LOGGER ENGINE
# ==========================================
class DataLogger:
    def __init__(self, imu, pmic):
        self.imu = imu
        self.pmic = pmic
        self.is_recording = False
        self.file = None
        self.start_time = 0
        self.last_elapsed_sec = 0
        self.filename = "run_data.csv"
        
        self.bat_pct = 100
        self.last_slow_check = 0
        
        # Buffer & Memory Protection settings
        self.buffer = []
        self.BUFFER_SIZE = 50           # Writes to Flash every 500ms (50 readings)
        self.MAX_DURATION_MS = 180000   # 3 minutes maximum
        self.MAX_LINES = 18000          # 100Hz * 60s * 3m = 18000
        self.current_lines = 0
        
        # Storage tracking
        self.SAFE_MARGIN_BYTES = 102400
        self.free_bytes = 0
        self.total_bytes = 1 # Avoid div by zero
        self.storage_pct = 0
        self.update_storage_stats()

    def update_storage_stats(self):
        try:
            stats = os.statvfs('/')
            block_size = stats[0]
            total_blocks = stats[2]
            free_blocks = stats[3]
            
            self.total_bytes = block_size * total_blocks
            self.free_bytes = block_size * free_blocks
            
            if self.total_bytes > 0:
                self.storage_pct = int((self.free_bytes / self.total_bytes) * 100)
        except Exception:
            self.free_bytes = 0
            self.total_bytes = 1
            self.storage_pct = 0

    def start(self):
        if self.is_recording:
            return
        self.update_storage_stats()
        if self.free_bytes < self.SAFE_MARGIN_BYTES:
            print("Not enough storage to start.")
            return
            
        try:
            self.file = open(self.filename, "w")
            self.file.write("time_ms,ax,ay,az,gx,gy,gz\n")
            self.buffer = []
            self.current_lines = 0
            self.last_elapsed_sec = 0
            self.is_recording = True
            self.start_time = time.ticks_ms()
        except Exception as e:
            print("Failed to open file:", e)

    def stop(self):
        self.is_recording = False
        if self.start_time > 0:
            self.last_elapsed_sec = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000
            
        if self.file:
            try:
                # Flush remaining buffer before closing
                if len(self.buffer) > 0:
                    self.file.write("".join(self.buffer))
                    self.buffer = []
                self.file.flush()
                self.file.close()
            except Exception as e:
                print("Error closing file:", e)
            self.file = None
        self.update_storage_stats()
        gc.collect()

    def update(self, current_time_ms):
        if time.ticks_diff(current_time_ms, self.last_slow_check) > 5000:
            self.bat_pct = self.pmic.get_battery_level()
            self.update_storage_stats()
            
            if self.is_recording and self.free_bytes < self.SAFE_MARGIN_BYTES:
                print("Safety Margin Hit! Auto-stopping recording.")
                self.stop()
                
            self.last_slow_check = current_time_ms

        if self.is_recording and self.file:
            t = time.ticks_diff(current_time_ms, self.start_time)
            
            # Auto-Stop trigger
            if t >= self.MAX_DURATION_MS or self.current_lines >= self.MAX_LINES:
                self.stop()
                return
                
            data = self.imu.get_data()
            
            # Append string to RAM list instead of writing directly to flash
            self.buffer.append("{},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}\n".format(t, *data))
            self.current_lines += 1
            
            # Flush to file in batches
            if len(self.buffer) >= self.BUFFER_SIZE:
                try:
                    self.file.write("".join(self.buffer))
                    self.buffer = []
                except Exception as e:
                    print("Write error:", e)
                    self.stop()

    def has_data(self):
        try:
            return os.stat(self.filename)[6] > 0
        except OSError:
            return False

    def get_status(self):
        if self.is_recording:
            elapsed = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000
        else:
            elapsed = self.last_elapsed_sec
            
        return {
            "recording": self.is_recording,
            "has_data": self.has_data(),
            "bat": self.bat_pct,
            "storage_pct": self.storage_pct,
            "elapsed_time": elapsed
        }

# ==========================================
# SYSTEM SETUP: ACCESS POINT
# ==========================================
def setup_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="Equilibrium_M5", password="12345678", authmode=3)
    while not ap.active():
        time.sleep(0.5)
    return ap.ifconfig()[0]

def main():
    machine.freq(80000000)

    power_hold = machine.Pin(4, machine.Pin.OUT)
    power_hold.value(1)

    backlight = machine.Pin(27, machine.Pin.OUT)
    backlight.value(1)
    time.sleep(1.5)
    backlight.value(0)

    status_led = machine.Pin(19, machine.Pin.OUT)
    status_led.value(0) 

    btn_m5 = machine.Pin(37, machine.Pin.IN, machine.Pin.PULL_UP)

    i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
    imu = MPU6886(i2c)
    pmic = StickPlus2Battery()
    logger = DataLogger(imu, pmic)

    setup_ap()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", 80))
    s.listen(5)
    s.setblocking(False)

    poller = select.poll()
    poller.register(s, select.POLLIN)

    client_conn = None
    last_engine_update = time.ticks_ms()
    last_heartbeat = time.ticks_ms()

    HTML_BYTES = HTML_PAGE.encode("utf-8")
    HTTP_HTML_FULL = (b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: %d\r\n\r\n%s" % (len(HTML_BYTES), HTML_BYTES))
    HTTP_OK = b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nOK"

    while True:
        now = time.ticks_ms()
        
        # Strict Timing: Use ticks_diff against an advancing deadline (no drift)
        if time.ticks_diff(now, last_engine_update) >= 10:
            logger.update(now)
            # Advance exactly 10ms from the last schedule, ensuring long-term 100Hz precision
            last_engine_update = time.ticks_add(last_engine_update, 10)

        if time.ticks_diff(now, last_heartbeat) >= (500 if logger.is_recording else 2000):
            status_led.value(1)
            time.sleep_ms(10)
            status_led.value(0)
            last_heartbeat = now

        if btn_m5.value() == 0:
            logger.stop() 
            for _ in range(3):
                backlight.value(1)
                time.sleep_ms(150)
                backlight.value(0)
                time.sleep_ms(150)
            power_hold.value(0)
            while True:
                pass

        events = poller.poll(0)

        for sock, ev in events:
            if sock == s:
                try:
                    new_conn, addr = s.accept()
                    new_conn.settimeout(0.5)

                    if client_conn:
                        poller.unregister(client_conn)
                        try: client_conn.close()
                        except: pass

                    client_conn = new_conn
                    poller.register(client_conn, select.POLLIN)
                except OSError:
                    pass

            elif sock == client_conn:
                try:
                    request = client_conn.recv(1024)

                    if not request:
                        poller.unregister(client_conn)
                        client_conn.close()
                        client_conn = None
                        continue

                    if b"GET /status" in request:
                        payload = json.dumps(logger.get_status()).encode("utf-8")
                        res = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: %d\r\n\r\n%s" % (len(payload), payload))
                        client_conn.sendall(res)

                    elif b"GET /start" in request:
                        logger.start()
                        client_conn.sendall(HTTP_OK)

                    elif b"GET /stop" in request:
                        logger.stop()
                        client_conn.sendall(HTTP_OK)
                        
                    elif b"GET /download" in request:
                        client_conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/csv\r\nContent-Disposition: attachment; filename=\"run_data.csv\"\r\nConnection: close\r\n\r\n")
                        try:
                            with open(logger.filename, "r") as f:
                                while True:
                                    chunk = f.read(1024)
                                    if not chunk: break
                                    client_conn.sendall(chunk)
                        except OSError:
                            pass

                    elif b"GET / " in request:
                        client_conn.sendall(HTTP_HTML_FULL)

                    poller.unregister(client_conn)
                    client_conn.close()
                    client_conn = None

                except Exception:
                    poller.unregister(client_conn)
                    try: client_conn.close()
                    except: pass
                    client_conn = None

if __name__ == "__main__":
    main()