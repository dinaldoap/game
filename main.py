import gc
import json
import math
import os
import select
import socket
import time
import struct

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
        :root { --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8; --primary: #2563eb; --danger: #ef4444; --success: #10b981; --border: #334155; --accent: #60a5fa; --warning: #f59e0b; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, sans-serif; user-select: none; }
        body { background-color: var(--bg); color: var(--text); touch-action: manipulation; display: flex; flex-direction: column; height: 100vh; width: 100vw; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 400px; width: 100%; text-align: center; display: flex; flex-direction: column; gap: 20px; }
        .card { background-color: var(--card); padding: 24px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid var(--border); }
        h1 { color: var(--accent); font-size: 2rem; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .version-badge { font-size: 0.9rem; color: var(--muted); font-weight: normal; vertical-align: super; }
        p { color: var(--muted); text-align: center; margin-bottom: 10px; }
        
        button { width: 100%; color: white; border: none; padding: 18px 30px; border-radius: 50px; font-size: 1.2rem; font-weight: bold; cursor: pointer; transition: transform 0.1s; margin-top: 10px; }
        button:active:not(:disabled) { transform: scale(0.96); }
        button:disabled { opacity: 0.35; cursor: not-allowed; }
        
        .btn-start { background-color: var(--success); }
        .btn-stop { background-color: var(--danger); }
        .btn-download { background-color: var(--primary); }
        
        .status-bar { position: absolute; top: 15px; width: 100%; padding: 0 15px; display: flex; justify-content: space-between; align-items: flex-start; z-index: 100; pointer-events: none; }
        .right-badges { display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
        .badge-ui { background: rgba(0,0,0,0.5); padding: 5px 12px; border-radius: 20px; font-size: 0.9rem; font-weight: bold; border: 1px solid var(--border); box-shadow: 0 2px 10px rgba(0,0,0,0.5); }
        .wifi-status { color: #4ade80; }
        .bat-status, .ram-status, .time-indicator { color: var(--accent); transition: color 0.3s; }
        .status-indicator { margin-top: 10px; font-size: 1.2rem; font-weight: bold; color: var(--muted); }
        .time-indicator { margin-top: 5px; font-size: 0.9rem; margin-bottom: 15px; }
        .recording-pulse { color: var(--danger); animation: pulse 1.5s infinite; }
        .saving-pulse { color: var(--warning); animation: pulse 0.5s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="status-bar">
        <div id="wifi-status" class="badge-ui wifi-status">🟢 Connected</div>
        <div class="right-badges">
            <div id="bat-status" class="badge-ui bat-status">🔋 --%</div>
            <div id="ram-status" class="badge-ui ram-status">🧠 --%</div>
        </div>
    </div>
    <div class="container">
        <div class="card">
            <h1>Run Biomechanics <sup class="version-badge">v0.0.6</sup></h1>
            <p>Place device in central back pocket. (Logs at 100Hz, Auto-stops at ~3m)</p>
            <div id="status-text" class="status-indicator">Status: Idle</div>
            <div id="time-recorded-text" class="time-indicator">Time Recorded: 0m 0s</div>
            
            <button id="btn-start" class="btn-start" onclick="startRecording()">START RECORDING</button>
            <button id="btn-stop" class="btn-stop" onclick="stopRecording()" disabled>STOP RECORDING</button>
            <button id="btn-download" class="btn-download" onclick="downloadData()" disabled>DOWNLOAD CSV</button>
        </div>
    </div>
    <script>
        let isRecording = false; 
        let isSaving = false; 
        let hasData = false; 
        let isCountingDown = false;
        
        let isCommandPending = false; 
        let isFetchingStatus = false;
        
        const wifiStatus = document.getElementById('wifi-status'); 
        const batStatus = document.getElementById('bat-status');
        const ramStatus = document.getElementById('ram-status'); 
        const timeRecordedText = document.getElementById('time-recorded-text');
        const statusTextElem = document.getElementById('status-text');
        
        const btnStart = document.getElementById('btn-start'); 
        const btnStop = document.getElementById('btn-stop'); 
        const btnDownload = document.getElementById('btn-download');

        function formatTime(seconds) {
            let h = Math.floor(seconds / 3600); let m = Math.floor((seconds % 3600) / 60); let s = seconds % 60;
            return h > 0 ? `${h}h ${m}m ${s}s` : `${m}m ${s}s`;
        }

        const fetchWithTimeout = (url, ms) => Promise.race([
            fetch(url),
            new Promise((_, reject) => setTimeout(() => reject(new Error("Timeout")), ms))
        ]);

        function renderStateMachine() {
            if (isCountingDown) return; 

            if (isSaving) {
                btnStart.disabled = true; btnStart.innerText = 'START RECORDING';
                btnStop.disabled = true; btnStop.innerText = 'STOP RECORDING';
                btnDownload.disabled = true;
                statusTextElem.innerHTML = 'Status: <span class="saving-pulse">SAVING TO FLASH...</span>';
                timeRecordedText.style.color = "var(--warning)";
            } 
            else if (isRecording) {
                btnStart.disabled = true; btnStart.innerText = 'RECORDING';
                btnStop.disabled = false; btnStop.innerText = 'STOP RECORDING';
                btnDownload.disabled = true;
                statusTextElem.innerHTML = 'Status: <span class="recording-pulse">RECORDING...</span>';
                timeRecordedText.style.color = "var(--danger)";
            } 
            else {
                btnStart.disabled = false; btnStart.innerText = 'START RECORDING';
                btnStop.disabled = true; btnStop.innerText = 'STOP RECORDING';
                btnDownload.disabled = !hasData;
                statusTextElem.innerHTML = 'Status: Idle';
                timeRecordedText.style.color = "var(--accent)";
            }
        }

        async function updateStatus() {
            if (isCountingDown || isCommandPending || isFetchingStatus) return; 
            
            isFetchingStatus = true;
            try {
                let res = await fetchWithTimeout(`/status?t=${Date.now()}`, 2000);
                if (!res.ok) throw new Error("Network error");
                
                wifiStatus.innerText = '🟢 Connected'; 
                wifiStatus.style.color = '#4ade80';
                
                let data = await res.json();
                
                isRecording = data.recording; 
                isSaving = data.saving; 
                hasData = data.has_data;
                
                batStatus.innerText = `🔋 ${data.bat}%`; 
                batStatus.style.color = data.bat <= 20 ? "#ef4444" : "var(--accent)";
                ramStatus.innerText = `🧠 ${data.ram_pct}%`; 
                ramStatus.style.color = data.ram_pct <= 10 ? "#ef4444" : "var(--accent)";
                timeRecordedText.innerText = `Time Recorded: ${formatTime(data.elapsed_time)}`;
                
                renderStateMachine();

            } catch (e) {
                wifiStatus.innerText = '🔴 Offline'; 
                wifiStatus.style.color = '#ef4444';
            } finally {
                isFetchingStatus = false;
            }
        }

        async function startRecording() {
            if (hasData && !confirm("Starting a new recording will overwrite the existing data. Continue?")) return;
            
            isCountingDown = true;
            isCommandPending = true; 
            
            btnStart.disabled = true;
            btnStop.disabled = true;
            btnDownload.disabled = true;
            timeRecordedText.innerText = "Time Recorded: 0m 0s";
            timeRecordedText.style.color = "var(--accent)";
            
            for(let i = 3; i > 0; i--) { 
                btnStart.innerText = i + "..."; 
                await new Promise(resolve => setTimeout(resolve, 1000)); 
            }
            btnStart.innerText = "GO!"; 
            await new Promise(resolve => setTimeout(resolve, 500)); 
            
            try { 
                await fetchWithTimeout(`/start?t=${Date.now()}`, 3000); 
            } catch (e) { 
                console.error("Start command failed:", e); 
            }
            
            isRecording = true;
            isSaving = false;
            isCountingDown = false; 
            isCommandPending = false; 
            renderStateMachine();
        }

        async function stopRecording() {
            isCommandPending = true; 
            btnStop.disabled = true; 
            btnStop.innerText = 'STOPPING...';
            
            try { 
                await fetchWithTimeout(`/stop?t=${Date.now()}`, 3000); 
            } catch (e) { 
                console.error(e); 
            }
            
            isRecording = false;
            isSaving = true;
            isCommandPending = false;
            
            renderStateMachine();
            updateStatus(); 
        }
        
        function downloadData() { window.location.href = '/download'; }
        
        setInterval(updateStatus, 1000); 
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
        self.connected = False

        try:
            self.i2c.writeto_mem(self.addr, 0x6B, b"\x00")
            time.sleep_ms(10)
            self.i2c.writeto_mem(self.addr, 0x1A, b"\x02") # LPF 98Hz
            self.i2c.writeto_mem(self.addr, 0x19, b"\x04") # ODR 200Hz
            self.i2c.writeto_mem(self.addr, 0x1B, b"\x18") # Gyro +- 2000dps
            self.i2c.writeto_mem(self.addr, 0x1C, b"\x18") # Accel +- 16g
            self.i2c.writeto_mem(self.addr, 0x1D, b"\x02") # Accel LPF 99Hz
            self.connected = True
        except OSError:
            self.connected = False

# ==========================================
# EDGE COMPUTING - ASYNC MICRO-STEPPED LOGGER
# ==========================================
class DataLogger:
    def __init__(self, imu, pmic):
        self.imu = imu
        self.pmic = pmic
        self.is_recording = False
        self.is_saving = False
        self.filename = "run_data.csv"
        
        self.bat_pct = 100
        self.ram_pct = 100
        self.last_slow_check = 0
        
        self.SAMPLE_SIZE = 18 
        self.CHUNK_SAMPLES = 500
        self.MAX_RECORD_SAMPLES = 18000 # Limite rígido de 3 minutos
        
        self.buffers = []
        self.max_samples = 0
        self.current_idx = 0
        
        self.start_time = 0
        self.last_elapsed_sec = 0
        self.auto_stop_flag = False
        
        # Async Dump Tracking
        self.dump_file = None
        self.dump_chunk_idx = 0
        self.dump_sample_idx = 0 # Adicionado para Micro-stepping
        
        self.update_ram_stats()

    def update_ram_stats(self):
        gc.collect()
        total_ram = 110000
        free_ram = gc.mem_free()
        if self.buffers:
            used = self.current_idx * self.SAMPLE_SIZE
            total_allocated = self.max_samples * self.SAMPLE_SIZE
            self.ram_pct = max(0, 100 - int((used / total_allocated) * 100)) if total_allocated > 0 else 0
        else:
            self.ram_pct = int((free_ram / total_ram) * 100)
            if self.ram_pct > 100: self.ram_pct = 100

    def update(self, current_time_ms):
        if not self.is_recording:
            return
            
        elapsed = time.ticks_diff(current_time_ms, self.start_time)
        
        if self.current_idx >= self.max_samples:
            self.auto_stop_flag = True
            return
            
        chunk_idx = self.current_idx // self.CHUNK_SAMPLES
        if chunk_idx >= len(self.buffers):
            self.auto_stop_flag = True
            return
            
        try:
            buf = self.buffers[chunk_idx]
            local_idx = self.current_idx % self.CHUNK_SAMPLES
            offset = local_idx * self.SAMPLE_SIZE
            
            raw_data = self.imu.i2c.readfrom_mem(self.imu.addr, 0x3B, 14)
            struct.pack_into("<L14s", buf, offset, elapsed, raw_data)
            self.current_idx += 1
        except Exception:
            pass

    def start(self):
        if self.is_recording or self.is_saving: return
        
        gc.collect()
        free_ram = gc.mem_free()
        safe_ram = max(0, free_ram - 30000)
        
        num_chunks_possible = safe_ram // (self.CHUNK_SAMPLES * self.SAMPLE_SIZE)
        num_chunks_needed = (self.MAX_RECORD_SAMPLES // self.CHUNK_SAMPLES) + 1
        num_chunks = min(num_chunks_possible, num_chunks_needed)
        
        self.buffers = []
        for _ in range(num_chunks):
            try:
                self.buffers.append(bytearray(self.CHUNK_SAMPLES * self.SAMPLE_SIZE))
            except MemoryError:
                break
                
        if len(self.buffers) == 0:
            print("Insufficient RAM.")
            return
            
        self.max_samples = min(self.MAX_RECORD_SAMPLES, len(self.buffers) * self.CHUNK_SAMPLES)
        self.current_idx = 0
        self.last_elapsed_sec = 0
        self.auto_stop_flag = False
        
        self.start_time = time.ticks_ms()
        self.is_recording = True

    def stop(self):
        if not self.is_recording: return
        self.is_recording = False
        if self.start_time > 0:
            self.last_elapsed_sec = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000
        self._start_async_dump()

    def _start_async_dump(self):
        self.is_saving = True
        self.dump_chunk_idx = 0
        self.dump_sample_idx = 0
        try:
            self.dump_file = open(self.filename, "w")
            self.dump_file.write("time_ms,ax,ay,az,gx,gy,gz\n")
        except Exception as e:
            print("Error opening file:", e)
            self._cleanup()

    def process_dump_step(self):
        """Micro-stepping: Processa apenas 50 linhas por ciclo para não travar a CPU e o Wi-Fi"""
        if not self.dump_file or not self.buffers:
            self._cleanup()
            return
            
        if self.dump_chunk_idx >= len(self.buffers):
            self.dump_file.close()
            self._cleanup()
            return
            
        chunk_idx = self.dump_chunk_idx
        buf = self.buffers[chunk_idx]
        
        samples_in_chunk = self.CHUNK_SAMPLES
        if chunk_idx == self.current_idx // self.CHUNK_SAMPLES:
            samples_in_chunk = self.current_idx % self.CHUNK_SAMPLES
            
        if chunk_idx > self.current_idx // self.CHUNK_SAMPLES or samples_in_chunk == 0:
            self.dump_file.close()
            self._cleanup()
            return

        a_res = 2048.0 
        g_res = 16.4   
        
        def to_signed(msb, lsb):
            val = (msb << 8) | lsb
            return val if val < 32768 else val - 65536

        chunk_str = []
        
        # PROCESSA NO MÁXIMO 50 LINHAS POR CICLO (Rápido o suficiente para o Wi-Fi não cair)
        lines_to_process = min(50, samples_in_chunk - self.dump_sample_idx)
        
        for _ in range(lines_to_process):
            offset = self.dump_sample_idx * self.SAMPLE_SIZE
            elapsed, raw = struct.unpack_from("<L14s", buf, offset)
            
            ax = to_signed(raw[0], raw[1]) / a_res
            ay = to_signed(raw[2], raw[3]) / a_res
            az = to_signed(raw[4], raw[5]) / a_res
            gx = to_signed(raw[8], raw[9]) / g_res
            gy = to_signed(raw[10], raw[11]) / g_res
            gz = to_signed(raw[12], raw[13]) / g_res
            
            chunk_str.append("{},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f},{:.4f}\n".format(elapsed, ax, ay, az, gx, gy, gz))
            self.dump_sample_idx += 1
            
        if chunk_str:
            self.dump_file.write("".join(chunk_str))
            
        # Move para o próximo chunk se esse acabou
        if self.dump_sample_idx >= samples_in_chunk:
            self.dump_chunk_idx += 1
            self.dump_sample_idx = 0
            
        # Verifica se o processo total terminou
        if self.dump_chunk_idx >= len(self.buffers) or self.dump_chunk_idx > (self.current_idx // self.CHUNK_SAMPLES):
            self.dump_file.close()
            self._cleanup()

    def _cleanup(self):
        self.dump_file = None
        self.buffers = []
        gc.collect()
        self.is_saving = False
        self.update_ram_stats()

    def process_background_tasks(self, current_time_ms):
        if self.auto_stop_flag:
            self.stop()
            self.auto_stop_flag = False
            return
            
        if self.is_saving:
            self.process_dump_step()
            return

        if time.ticks_diff(current_time_ms, self.last_slow_check) > 5000:
            self.bat_pct = self.pmic.get_battery_level()
            self.update_ram_stats()
            self.last_slow_check = current_time_ms

    def has_data(self):
        try: return os.stat(self.filename)[6] > 0
        except OSError: return False

    def get_status(self):
        elapsed = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000 if self.is_recording else self.last_elapsed_sec
        return { 
            "recording": self.is_recording, 
            "saving": self.is_saving,
            "has_data": self.has_data(), 
            "bat": self.bat_pct, 
            "ram_pct": self.ram_pct, 
            "elapsed_time": elapsed 
        }

# ==========================================
# SYSTEM SETUP: ACCESS POINT
# ==========================================
def setup_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="Equilibrium_M5", password="12345678", authmode=3)
    while not ap.active(): time.sleep(0.5)
    return ap.ifconfig()[0]

def main():
    machine.freq(80000000)

    power_hold = machine.Pin(4, machine.Pin.OUT); power_hold.value(1)
    backlight = machine.Pin(27, machine.Pin.OUT); backlight.value(1); time.sleep(1.5); backlight.value(0)
    status_led = machine.Pin(19, machine.Pin.OUT); status_led.value(0) 
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
    last_heartbeat = time.ticks_ms()
    last_engine_update = time.ticks_ms()

    HTML_BYTES = HTML_PAGE.encode("utf-8")
    HTTP_HTML_FULL = (b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: %d\r\n\r\n%s" % (len(HTML_BYTES), HTML_BYTES))
    HTTP_OK = (b"HTTP/1.1 200 OK\r\n"
               b"Cache-Control: no-store, max-age=0\r\n"
               b"Connection: close\r\n\r\nOK")

    while True:
        now = time.ticks_ms()
        
        if logger.is_recording:
            if time.ticks_diff(now, last_engine_update) >= 10:
                logger.update(now)
                last_engine_update = time.ticks_add(last_engine_update, 10)
        else:
            last_engine_update = now 
            
        logger.process_background_tasks(now)

        if time.ticks_diff(now, last_heartbeat) >= (500 if logger.is_recording else 2000):
            status_led.value(1); time.sleep_ms(10); status_led.value(0)
            last_heartbeat = now

        if btn_m5.value() == 0:
            logger.stop() 
            for _ in range(3):
                backlight.value(1); time.sleep_ms(150); backlight.value(0); time.sleep_ms(150)
            power_hold.value(0)
            while True: pass

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
                except OSError: pass

            elif sock == client_conn:
                try:
                    request = client_conn.recv(1024)
                    if not request:
                        poller.unregister(client_conn); client_conn.close(); client_conn = None
                        continue

                    if b"GET /status" in request:
                        payload = json.dumps(logger.get_status()).encode("utf-8")
                        client_conn.sendall(b"HTTP/1.1 200 OK\r\n"
                                            b"Content-Type: application/json\r\n"
                                            b"Cache-Control: no-store, max-age=0\r\n"
                                            b"Connection: close\r\n"
                                            b"Content-Length: %d\r\n\r\n%s" % (len(payload), payload))
                    elif b"GET /start" in request:
                        logger.start(); client_conn.sendall(HTTP_OK)
                    elif b"GET /stop" in request:
                        logger.stop(); client_conn.sendall(HTTP_OK)
                    elif b"GET /download" in request:
                        client_conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/csv\r\nContent-Disposition: attachment; filename=\"run_data.csv\"\r\nConnection: close\r\n\r\n")
                        try:
                            with open(logger.filename, "r") as f:
                                while True:
                                    chunk = f.read(1024)
                                    if not chunk: break
                                    client_conn.sendall(chunk)
                        except OSError: pass
                    elif b"GET / " in request:
                        client_conn.sendall(HTTP_HTML_FULL)

                    poller.unregister(client_conn); client_conn.close(); client_conn = None
                except Exception:
                    poller.unregister(client_conn)
                    try: client_conn.close()
                    except: pass
                    client_conn = None

if __name__ == "__main__":
    main()