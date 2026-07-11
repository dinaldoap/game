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

        .hidden { display: none !important; }
        .screen { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; }
        
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

        /* BATTERY INDICATOR STYLING */
        .bat-status { position: absolute; top: 15px; right: 15px; background: rgba(0,0,0,0.5); padding: 5px 12px; border-radius: 20px; font-size: 0.9rem; font-weight: bold; color: var(--accent); border: 1px solid var(--border); z-index: 100; box-shadow: 0 2px 10px rgba(0,0,0,0.5); }
    </style>
</head>
<body>
    <div id="bat-status" class="bat-status">🔋 --%</div>

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
        const batStatus = document.getElementById('bat-status');

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
            if (!isPlaying) {
                // Keep polling slowly in background just for battery when not playing
                setTimeout(backgroundPoll, 2000);
                return;
            }
            await processIMU();
            imuTimeout = setTimeout(pollIMU, 80); 
        }

        async function backgroundPoll() {
            if (isPlaying) return;
            const data = await fetchIMU();
            if (data && data.bat !== undefined) {
                batStatus.innerText = `🔋 ${data.bat}%`;
                if (data.bat <= 20) batStatus.style.color = "#ef4444";
                else batStatus.style.color = "var(--accent)";
            }
            setTimeout(backgroundPoll, 2000);
        }

        async function processIMU() {
            const data = await fetchIMU();
            if (!data) return; 
            
            // UPDATE BATTERY UI
            if (data.bat !== undefined) {
                batStatus.innerText = `🔋 ${data.bat}%`;
                if (data.bat <= 20) batStatus.style.color = "#ef4444";
                else batStatus.style.color = "var(--accent)";
            }

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
            backgroundPoll(); // Resume background battery polling
        }
        function resetGame() { switchScreen('home'); }
        
        // Start background polling on load
        backgroundPoll();
    </script>
</body>
</html>"""

# ==========================================
# BATTERY MONITOR (M5StickC Plus 2)
# ==========================================
class StickPlus2Battery:
    def __init__(self):
        # The Plus 2 reads battery voltage via an internal divider on Pin 38
        self.adc = machine.ADC(machine.Pin(38))
        self.adc.atten(machine.ADC.ATTN_11DB) # Configure for wider voltage range
        self.adc.width(machine.ADC.WIDTH_12BIT)

    def get_battery_level(self):
        try:
            raw = self.adc.read()
            # On the Plus 2, the 12-bit ADC reads ~2600 at 4.2V (100% full) 
            # and roughly ~1900 at 3.2V (0% empty)
            pct = ((raw - 1900) / 700.0) * 100
            return max(0, min(100, int(pct)))
        except Exception:
            return 100 # Fallback so the game doesn't crash if reading fails

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

        try:
            self.i2c.writeto_mem(self.addr, 0x6B, b'\x00') 
            time.sleep_ms(10)
            self.i2c.writeto_mem(self.addr, 0x1C, b'\x10') 
            self.i2c.writeto_mem(self.addr, 0x1B, b'\x18') 
            self.connected = True
        except OSError:
            self.connected = False

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
    def __init__(self, imu, pmic):
        self.imu = imu
        self.pmic = pmic
        self.baseline = None
        self.last_data = None  # Tracks immediate previous frame for stability
        self.stable_frames = 0
        
        # --- TUNED FOR BREATHING INSENSITIVITY ---
        self.GYRO_DEADZONE = 8.0      # Was 3.0: Ignores slow rotational chest movement
        self.ACCEL_DEADZONE = 0.20    # Was 0.08: Ignores linear chest expansion
        self.ACCEL_WEIGHT = 70.0      # Was 100.0: Reduces harshness of linear shifts
        self.PENALTY_MULTIPLIER = 0.3 # Was 0.5: Slows down the point drain
        
        self.accumulated_penalty = 0.0
        self.bx = 50.0
        self.by = 50.0
        
        # Battery state
        self.bat_pct = 100
        self.last_bat_check = 0

    def calibrate(self):
        self.baseline = self.imu.get_data()
        self.last_data = self.baseline
        self.stable_frames = 0
        self.accumulated_penalty = 0.0
        self.bx = 50.0
        self.by = 50.0

    def update(self):
        # 1. Fetch Current Data
        data = self.imu.get_data()
        
        if not self.baseline:
            self.baseline = data
        if not self.last_data:
            self.last_data = data
            
        # 2. Check Frame-to-Frame Stability (Are they holding still RIGHT NOW?)
        inst_ax = data[0] - self.last_data[0]
        inst_ay = data[1] - self.last_data[1]
        inst_az = data[2] - self.last_data[2]
        inst_accel_shift = math.sqrt(inst_ax**2 + inst_ay**2 + inst_az**2)
        
        inst_gx = data[3] - self.last_data[3]
        inst_gy = data[4] - self.last_data[4]
        inst_gz = data[5] - self.last_data[5]
        inst_gyro_shift = math.sqrt(inst_gx**2 + inst_gy**2 + inst_gz**2)
        
        # If instantaneous movement is very low, they stopped moving
        if inst_gyro_shift < 1.5 and inst_accel_shift < 0.02:
            self.stable_frames += 1
            if self.stable_frames > 15:
                # Re-calibrate baseline to this new bent position!
                self.baseline = data 
                self.stable_frames = 0
        else:
            self.stable_frames = 0
            
        # Update last_data for the next loop
        self.last_data = data 
            
        # 3. Calculate Wobble against the CURRENT Baseline to apply penalties
        gx = data[3] - self.baseline[3]
        gy = data[4] - self.baseline[4]
        gz = data[5] - self.baseline[5]
        gyro_wobble = math.sqrt(gx**2 + gy**2 + gz**2)
        
        ax = data[0] - self.baseline[0]
        ay = data[1] - self.baseline[1]
        az = data[2] - self.baseline[2]
        accel_shift = math.sqrt(ax**2 + ay**2 + az**2)
        
        # APPLY DEADZONES
        if gyro_wobble < self.GYRO_DEADZONE: gyro_wobble = 0
        if accel_shift < self.ACCEL_DEADZONE: accel_shift = 0
        
        combined = gyro_wobble + (accel_shift * self.ACCEL_WEIGHT)
        
        if combined > 0:
            self.accumulated_penalty += (combined * self.PENALTY_MULTIPLIER)
            self.bx = 50 + (gy * 0.5) + (ax * 40)
            self.by = 50 + (gx * 0.5) + (ay * 40)
        else:
            self.bx = 50.0
            self.by = 50.0
            
        # 4. Update Battery (Throttled)
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_bat_check) > 5000:
            self.bat_pct = self.pmic.get_battery_level()
            self.last_bat_check = now

    def get_payload(self):
        p = self.accumulated_penalty
        self.accumulated_penalty = 0.0
        return {"p": p, "bx": self.bx, "by": self.by, "bat": self.bat_pct}

# ==========================================
# SYSTEM SETUP: ACCESS POINT (AP MODE)
# ==========================================
def setup_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    
    ssid = "Equilibrium_M5"
    password = "12345678"
    ap.config(essid=ssid, password=password, authmode=3)
    
    while not ap.active():
        time.sleep(0.5)
        
    return ap.ifconfig()[0]

def main():
    # --- EXTREME POWER SAVINGS ---
    # Drop CPU frequency to 80MHz. (Cuts CPU power consumption by ~50%)
    machine.freq(80000000)

    power_hold = machine.Pin(4, machine.Pin.OUT)
    power_hold.value(1)

    # Disable screen backlight (Saves ~15-20mA). 
    # Since the UI is strictly web-based, leaving the screen on wastes battery.
    backlight = machine.Pin(27, machine.Pin.OUT)
    backlight.value(0) 

    i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)
    imu = MPU6886(i2c)
    pmic = StickPlus2Battery()
    
    engine = GameEngine(imu, pmic)
    ip_address = setup_ap()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(5)
    s.setblocking(False) 

    # --- SERVER STARTUP LOG ---
    print("-" * 40)
    print("🚀 Equilibrium Game Server is UP and RUNNING!")
    print("📡 Wi-Fi SSID: Equilibrium_M5")
    print("🌐 Connect to: http://{}".format(ip_address))
    print("-" * 40)

    req_count = 0 
    last_engine_update = time.ticks_ms()

    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_engine_update) >= 20: 
            engine.update()
            last_engine_update = now

        try:
            conn, addr = s.accept()
            conn.settimeout(0.5) 
            
            request = conn.recv(512).decode('utf-8')
            
            if not request:
                conn.close()
                continue
                
            if request.startswith('GET /data'):
                response_data = json.dumps(engine.get_payload())
                conn.send('HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n'.encode('utf-8'))
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
            # Yield CPU to idle. This stops the endless while True 
            # loop from running at 100% capacity, massive power saver.
            time.sleep_ms(5)
            
        except Exception as e:
            try:
                conn.close()
            except:
                pass

if __name__ == '__main__':
    main()