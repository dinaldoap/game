import network
import machine
import socket
import time
import json
import gc
import math

# ==========================================
# HTML INTERFACE (Embedded - 100% Offline)
# ==========================================
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Equilibrium Challenge</title>
    <style>
        :root {
            --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8;
            --primary: #2563eb; --primary-hover: #1d4ed8;
            --border: #334155; --accent: #60a5fa;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, sans-serif; user-select: none; }
        body { background-color: var(--bg); color: var(--text); touch-action: manipulation; display: flex; flex-direction: column; height: 100vh; width: 100vw; overflow: hidden; align-items: center; justify-content: center; padding: 20px; }
        
        .container { max-width: 400px; width: 100%; text-align: center; display: flex; flex-direction: column; gap: 20px; }
        .card { background-color: var(--card); padding: 24px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid var(--border); }
        h1 { color: var(--accent); font-size: 2.2rem; margin-bottom: 5px; }
        h2 { color: var(--accent); font-size: 1.8rem; }
        p, li { color: var(--muted); text-align: left; }
        ol { padding-left: 20px; margin-top: 10px; }
        li { margin-bottom: 10px; line-height: 1.4; }
        strong { color: var(--text); }
        
        button { width: 100%; background-color: var(--primary); color: white; border: none; padding: 18px 30px; border-radius: 50px; font-size: 1.2rem; font-weight: bold; cursor: pointer; transition: transform 0.1s, background-color 0.2s; margin-top: 10px; box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4); }
        button:active { background-color: var(--primary-hover); transform: scale(0.96); }
        button.secondary { background-color: var(--border); box-shadow: none; }
        button.secondary:active { background-color: #475569; }

        /* Core visibility class */
        .hidden { display: none !important; }
        
        /* Screens */
        .screen { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; }
        
        /* Game specific */
        .score-board { display: flex; justify-content: space-between; width: 100%; padding: 0 10px; font-weight: bold; font-size: 1.2rem; margin-bottom: 20px; }
        .score-board span { color: white; font-size: 1.8rem; display: block; margin-top: 5px;}
        
        .arena { position: relative; width: 260px; height: 260px; border-radius: 50%; border: 4px solid var(--border); background-color: var(--bg); overflow: hidden; display: flex; align-items: center; justify-content: center; box-shadow: inset 0 0 30px rgba(0,0,0,0.8); }
        .crosshair-h { position: absolute; width: 100%; height: 1px; background-color: rgba(255,255,255,0.15); }
        .crosshair-v { position: absolute; height: 100%; width: 1px; background-color: rgba(255,255,255,0.15); }
        .target-ring { position: absolute; width: 130px; height: 130px; border-radius: 50%; border: 1px dashed rgba(255,255,255,0.2); }
        .bubble { position: absolute; width: 32px; height: 32px; border-radius: 50%; background-color: var(--primary); box-shadow: 0 0 20px var(--accent); transition: top 0.08s ease-out, left 0.08s ease-out; z-index: 10; top: 50%; left: 50%; transform: translate(-50%, -50%); }
        
        .countdown { font-size: 8rem; font-weight: 900; color: white; margin-top: 20px; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(0.9); opacity: 0.8; } }
        
        .final-score { font-size: 4.5rem; font-weight: 900; color: var(--accent); margin: 15px 0; }
        .badge { padding: 6px 20px; border-radius: 20px; font-size: 1rem; font-weight: bold; text-transform: uppercase; border: 2px solid var(--primary); color: var(--accent); background-color: rgba(37, 99, 235, 0.15); }
    </style>
</head>
<body>
    <div id="screen-home" class="screen container">
        <div class="card">
            <h1>Equilibrium</h1>
            <p style="text-align: center; color: var(--accent);">Balance Challenge</p>
        </div>
        <div class="card">
            <h3 style="color: white; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 15px; text-align:left;">Instructions:</h3>
            <ol>
                <li>Hold M5Stick firmly against chest.</li>
                <li>Stand on <strong>one foot</strong>.</li>
                <li>Cross your arms over your chest.</li>
                <li>Press Start, then <strong>close your eyes</strong>.</li>
            </ol>
        </div>
        <button onclick="startCalibration()">START</button>
    </div>

    <div id="screen-calibrating" class="screen hidden">
        <h2>Get Ready!</h2>
        <div id="countdown-text" class="countdown">3</div>
    </div>

    <div id="screen-game" class="screen hidden container">
        <div class="score-board">
            <div style="color: var(--muted); text-align: left;">Time <span id="timer-text">30</span></div>
            <div style="color: var(--muted); text-align: right;">Score <span id="live-score-text">10000</span></div>
        </div>
        <div class="arena">
            <div class="crosshair-h"></div>
            <div class="crosshair-v"></div>
            <div class="target-ring"></div>
            <div id="wobble-bubble" class="bubble"></div>
        </div>
    </div>

    <div id="screen-results" class="screen hidden container">
        <h2>Round Over!</h2>
        <div class="card" style="display: flex; flex-direction: column; align-items: center;">
            <p style="text-align: center;">Final Score</p>
            <div id="final-score" class="final-score">8500</div>
            <div id="performance-badge" class="badge">Great</div>
        </div>
        <button class="secondary" onclick="resetGame()">TRY AGAIN</button>
    </div>

    <script>
        let maxScore = 10000, currentScore = maxScore, timeLeft = 30, isPlaying = false;
        let gameLoopInterval, imuTimeout; 
        let lastStumpTime = 0; 
        let audioCtx;

        function initAudio() {
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            if (audioCtx.state === 'suspended') audioCtx.resume();
        }

        function playTone(freq, type, duration, vol=0.1) {
            if(!audioCtx) return;
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
            gain.gain.setValueAtTime(vol, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + duration);
        }
        
        const screens = { home: document.getElementById('screen-home'), calibrating: document.getElementById('screen-calibrating'), game: document.getElementById('screen-game'), results: document.getElementById('screen-results') };
        const bubble = document.getElementById('wobble-bubble'), timerText = document.getElementById('timer-text'), liveScoreText = document.getElementById('live-score-text');

        function switchScreen(s) { 
            Object.values(screens).forEach(scr => scr.classList.add('hidden')); 
            screens[s].classList.remove('hidden'); 
        }

        async function fetchIMU() {
            try {
                const res = await fetch('/data', { signal: AbortSignal.timeout(200) });
                if (!res.ok) throw new Error("Network error");
                return await res.json();
            } catch (e) { 
                return null; 
            }
        }

        async function startCalibration() {
            initAudio(); 
            switchScreen('calibrating');
            let count = 3;
            document.getElementById('countdown-text').innerText = count;
            playTone(440, 'square', 0.2, 0.1);
            
            const iv = setInterval(async () => {
                count--;
                if (count > 0) {
                    document.getElementById('countdown-text').innerText = count;
                    playTone(440, 'square', 0.2, 0.1);
                } else { 
                    clearInterval(iv); 
                    try { await fetch('/calibrate'); } catch(e) { console.error("Calib failed"); }
                    playTone(880, 'square', 0.5, 0.15); 
                    startGame(); 
                }
            }, 1000);
        }

        function startGame() {
            switchScreen('game'); 
            isPlaying = true; 
            timeLeft = 30; 
            currentScore = maxScore;
            lastStumpTime = 0;
            
            liveScoreText.innerText = currentScore;
            timerText.innerText = timeLeft;
            bubble.style.left = '50%';
            bubble.style.top = '50%';

            gameLoopInterval = setInterval(() => { 
                timeLeft--; 
                timerText.innerText = timeLeft; 
                if (timeLeft <= 0) endGame(); 
            }, 1000);
            
            pollIMU(); 
        }

        async function pollIMU() {
            if (!isPlaying) return;
            await processIMU();
            imuTimeout = setTimeout(pollIMU, 80); 
        }

        async function processIMU() {
            const data = await fetchIMU();
            if (!data) return; 
            
            if (data.p > 0) {
                currentScore = Math.max(0, currentScore - Math.floor(data.p));
                liveScoreText.innerText = currentScore;
                
                const now = Date.now();
                if (data.p > 15 && (now - lastStumpTime > 300)) {
                    playTone(150, 'sawtooth', 0.1, 0.05); 
                    lastStumpTime = now;
                }
            }
            
            bubble.style.left = `${Math.max(5, Math.min(95, data.bx))}%`; 
            bubble.style.top = `${Math.max(5, Math.min(95, data.by))}%`;
        }

        function endGame() {
            isPlaying = false; 
            clearInterval(gameLoopInterval); 
            clearTimeout(imuTimeout); 
            
            playTone(150, 'square', 0.8, 0.2); 
            
            document.getElementById('final-score').innerText = currentScore;
            const b = document.getElementById('performance-badge');
            
            if (currentScore > 9000) { 
                b.innerText = "Master"; 
                b.style.borderColor = "#a855f7"; b.style.color = "#d8b4fe"; b.style.backgroundColor = "rgba(168, 85, 247, 0.15)";
            } else if (currentScore > 5000) { 
                b.innerText = "Good"; 
                b.style.borderColor = "#3b82f6"; b.style.color = "#93c5fd"; b.style.backgroundColor = "rgba(59, 130, 246, 0.15)";
            } else { 
                b.innerText = "Needs Practice"; 
                b.style.borderColor = "#ef4444"; b.style.color = "#fca5a5"; b.style.backgroundColor = "rgba(239, 68, 68, 0.15)";
            }
            switchScreen('results');
        }
        function resetGame() { switchScreen('home'); }
    </script>
</body>
</html>"""

# ==========================================
# MPU6886 FULL 6-AXIS DRIVER
# ==========================================
class MPU6886:
    def __init__(self, i2c):
        self.i2c = i2c
        self.addr = 0x68
        self.alpha = 0.3 # Global Low-Pass Filter
        
        self.f_ax, self.f_ay, self.f_az = 0.0, 0.0, 1.0
        self.f_gx, self.f_gy, self.f_gz = 0.0, 0.0, 0.0

        try:
            self.i2c.writeto_mem(self.addr, 0x6B, b'\x00') # Wake
            time.sleep_ms(10)
            self.i2c.writeto_mem(self.addr, 0x1C, b'\x10') # Accel 8G
            self.i2c.writeto_mem(self.addr, 0x1B, b'\x18') # Gyro 2000 dps
            self.connected = True
        except OSError:
            self.connected = False
            print("MPU6886 not found. Running in simulation mode.")

    def get_data(self):
        if not self.connected:
            return 0.0, 0.0, 1.0, 0.0, 0.0, 0.0
            
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

            return self.f_ax, self.f_ay, self.f_az, self.f_gx, self.f_gy, self.f_gz
            
        except OSError:
            return 0.0, 0.0, 1.0, 0.0, 0.0, 0.0

# ==========================================
# EDGE COMPUTING - GAME ENGINE
# ==========================================
class GameEngine:
    def __init__(self, imu):
        self.imu = imu
        self.baseline = None
        self.stable_frames = 0
        
        # FUSION TUNING PARAMETERS (Moved from JS)
        self.GYRO_DEADZONE = 3.0
        self.ACCEL_DEADZONE = 0.08
        self.ACCEL_WEIGHT = 100.0
        self.PENALTY_MULTIPLIER = 0.5
        
        # State
        self.accumulated_penalty = 0.0
        self.bx = 50.0
        self.by = 50.0

    def calibrate(self):
        self.baseline = self.imu.get_data()
        self.stable_frames = 0
        self.accumulated_penalty = 0.0
        self.bx = 50.0
        self.by = 50.0

    def update(self):
        data = self.imu.get_data()
        if not self.baseline:
            self.baseline = data
            
        # 1. Calculate Gyro Wobble
        gx = data[3] - self.baseline[3]
        gy = data[4] - self.baseline[4]
        gz = data[5] - self.baseline[5]
        gyro_wobble = math.sqrt(gx*gx + gy*gy + gz*gz)
        
        # 2. Calculate Accel Shift
        ax = data[0] - self.baseline[0]
        ay = data[1] - self.baseline[1]
        az = data[2] - self.baseline[2]
        accel_shift = math.sqrt(ax*ax + ay*ay + az*az)
        
        # 3. Auto-Zero Logic (Protects against sensor drift over time)
        if gyro_wobble < 1.5 and accel_shift < 0.05:
            self.stable_frames += 1
            if self.stable_frames > 15:
                self.baseline = data # Set new baseline silently
                self.stable_frames = 0
        else:
            self.stable_frames = 0
            
        # 4. Apply Deadzones
        if gyro_wobble < self.GYRO_DEADZONE: gyro_wobble = 0
        if accel_shift < self.ACCEL_DEADZONE: accel_shift = 0
        
        # 5. Sensor Fusion Logic
        combined = gyro_wobble + (accel_shift * self.ACCEL_WEIGHT)
        
        if combined > 0:
            # We ACCUMULATE the penalty. If the network drops a packet,
            # the next successful packet will send the total missed deduction.
            self.accumulated_penalty += (combined * self.PENALTY_MULTIPLIER)
            
            # Update visual bubble coordinates (constrained limits handled by JS)
            self.bx = 50 + (gy * 0.5) + (ax * 40)
            self.by = 50 + (gx * 0.5) + (ay * 40)
        else:
            self.bx = 50.0
            self.by = 50.0

    def get_payload(self):
        # Extract penalty and clear the accumulator for the next cycle
        p = self.accumulated_penalty
        self.accumulated_penalty = 0.0
        return {"p": p, "bx": self.bx, "by": self.by}

# ==========================================
# SYSTEM SETUP: ACCESS POINT (AP MODE)
# ==========================================
def setup_ap():
    # Configure device as Access Point
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    
    # Set SSID and Password (authmode 3 = WPA2-PSK)
    ssid = "Equilibrium_M5"
    password = "12345678"
    ap.config(essid=ssid, password=password, authmode=3)
    
    # Wait for AP to become active
    while not ap.active():
        time.sleep(0.5)
        
    ip = ap.ifconfig()[0]
    
    print("\n" + "="*40)
    print("🚀 M5Stick Access Point Ready!")
    print(f"📡 Connect your phone to Wi-Fi: {ssid}")
    print(f"🔑 Password: {password}")
    print(f"🌐 Then open browser at: http://{ip}")
    print("="*40 + "\n")
    
    return ip

def main():
    power_hold = machine.Pin(4, machine.Pin.OUT)
    power_hold.value(1)

    backlight = machine.Pin(27, machine.Pin.OUT)
    backlight.value(1)

    i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)
    imu = MPU6886(i2c)
    
    # Initialize Game Engine
    engine = GameEngine(imu)

    # Boot in AP Mode
    ip_address = setup_ap()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(5)
    
    # NON-BLOCKING SOCKET: Allows the Game Engine to run consistently
    s.setblocking(False) 
    print("Server is running...")

    req_count = 0 
    last_engine_update = time.ticks_ms()

    while True:
        # --- 1. EDGE PROCESSING CYCLE (Runs at ~50Hz) ---
        now = time.ticks_ms()
        if time.ticks_diff(now, last_engine_update) >= 20: 
            engine.update()
            last_engine_update = now

        # --- 2. NETWORK HANDLING CYCLE ---
        try:
            conn, addr = s.accept()
            conn.settimeout(0.5) 
            
            request = conn.recv(512).decode('utf-8')
            
            if not request:
                conn.close()
                continue
                
            if request.startswith('GET /data'):
                # Send the accumulated payload
                response_data = json.dumps(engine.get_payload())
                
                conn.send('HTTP/1.1 200 OK\r\n'.encode('utf-8'))
                conn.send('Content-Type: application/json\r\n'.encode('utf-8'))
                conn.send('Access-Control-Allow-Origin: *\r\n'.encode('utf-8'))
                conn.send('Connection: close\r\n\r\n'.encode('utf-8'))
                conn.send(response_data.encode('utf-8'))
                
            elif request.startswith('GET /calibrate'):
                engine.calibrate()
                conn.send('HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nOK'.encode('utf-8'))
                
            elif request.startswith('GET / '):
                conn.send('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n'.encode('utf-8'))
                conn.sendall(HTML_PAGE.encode('utf-8'))
                
            conn.close()
            
            req_count += 1
            if req_count > 50:
                gc.collect()
                req_count = 0
            
        except OSError:
            # Expected behavior for non-blocking socket when no request is waiting
            pass
        except Exception as e:
            try:
                conn.close()
            except:
                pass

if __name__ == '__main__':
    main()