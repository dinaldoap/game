import network
import machine
import socket
import time
import json
import gc

# ==========================================
# CONFIGURATION - MULTIPLE NETWORKS
# ==========================================
NETWORKS = [
    ('LOCALLINK-36194', 'V7870601x'),
]

# ==========================================
# HTML INTERFACE (Embedded)
# ==========================================
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Equilibrium Challenge</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: system-ui, sans-serif; touch-action: manipulation; }
        .bubble-transition { transition: top 0.1s ease-out, left 0.1s ease-out; }
        .pulse-animation { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .7; transform: scale(0.95); } }
    </style>
</head>
<body class="flex flex-col h-screen w-screen overflow-hidden items-center justify-center p-4">
    <div id="screen-home" class="flex flex-col items-center max-w-md w-full text-center space-y-6 transition-opacity duration-300">
        <div class="p-4 bg-slate-800 rounded-2xl shadow-xl w-full border border-slate-700">
            <h1 class="text-3xl font-bold text-blue-400 mb-2">Equilibrium</h1>
        </div>
        <div class="text-left bg-slate-800 p-6 rounded-2xl shadow-lg border border-slate-700 space-y-4 w-full">
            <h3 class="font-bold text-xl border-b border-slate-700 pb-2">Instructions:</h3>
            <ol class="list-decimal list-inside space-y-2 text-slate-300">
                <li>Hold M5Stick firmly against chest.</li>
                <li>Stand on <strong>one foot</strong>.</li>
                <li>Cross your arms over your chest.</li>
                <li>Press Start, then <strong>close your eyes</strong>.</li>
            </ol>
        </div>
        <button onclick="startCalibration()" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-4 px-8 rounded-full shadow-lg text-xl">START</button>
    </div>

    <div id="screen-calibrating" class="hidden flex-col items-center justify-center w-full h-full space-y-8">
        <h2 class="text-2xl font-bold text-blue-400">Get Ready!</h2>
        <div id="countdown-text" class="text-8xl font-black text-white pulse-animation">3</div>
    </div>

    <div id="screen-game" class="hidden flex-col items-center w-full max-w-md space-y-8">
        <div class="flex justify-between w-full px-4 items-center">
            <div class="text-slate-400 font-semibold">Time: <span id="timer-text" class="text-white text-2xl">30</span>s</div>
            <div class="text-slate-400 font-semibold text-right">Score: <span id="live-score-text" class="text-white text-2xl">10000</span></div>
        </div>
        <div class="relative w-64 h-64 rounded-full border-4 border-slate-600 bg-slate-800 shadow-inner flex items-center justify-center overflow-hidden">
            <div class="absolute w-full h-px bg-slate-600/50"></div>
            <div class="absolute h-full w-px bg-slate-600/50"></div>
            <div class="absolute w-32 h-32 rounded-full border border-slate-600/50"></div>
            <div id="wobble-bubble" class="absolute w-8 h-8 rounded-full bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.8)] bubble-transition z-10" style="top: 50%; left: 50%; transform: translate(-50%, -50%);"></div>
        </div>
    </div>

    <div id="screen-results" class="hidden flex-col items-center max-w-md w-full space-y-6">
        <h2 class="text-3xl font-bold text-slate-100">Round Over!</h2>
        <div class="bg-slate-800 p-8 rounded-3xl shadow-2xl border border-slate-700 w-full flex flex-col items-center">
            <p class="text-slate-400 font-medium mb-2">Final Score</p>
            <div id="final-score" class="text-6xl font-black text-blue-400 mb-4">8500</div>
            <div id="performance-badge" class="px-4 py-1 rounded-full text-sm font-bold uppercase bg-blue-900/50 text-blue-300 border border-blue-700">Great</div>
        </div>
        <button onclick="resetGame()" class="w-full bg-slate-700 hover:bg-slate-600 text-white font-bold py-4 px-8 rounded-full shadow-lg text-lg">TRY AGAIN</button>
    </div>

    <script>
        let maxScore = 10000, currentScore = maxScore, timeLeft = 30, isPlaying = false;
        let gameLoopInterval, imuInterval, baseline = null, previousData = null; 
        
        // --- Web Audio API Engine ---
        let audioCtx;
        let bgmInterval;

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

        function playBGM() {
            let step = 0;
            // A simple relaxing repeating pattern during the game
            const notes = [261.6, 329.6, 392.0, 329.6]; 
            bgmInterval = setInterval(() => {
                playTone(notes[step % 4], 'sine', 0.4, 0.03);
                step++;
            }, 500);
        }
        function stopBGM() { clearInterval(bgmInterval); }
        // ----------------------------
        
        const screens = { home: document.getElementById('screen-home'), calibrating: document.getElementById('screen-calibrating'), game: document.getElementById('screen-game'), results: document.getElementById('screen-results') };
        const bubble = document.getElementById('wobble-bubble'), timerText = document.getElementById('timer-text'), liveScoreText = document.getElementById('live-score-text');

        function switchScreen(s) { Object.values(screens).forEach(scr => scr.classList.add('hidden')); screens[s].classList.remove('hidden'); screens[s].classList.add('flex'); }

        async function fetchIMU() {
            try {
                const res = await fetch('/data', { signal: AbortSignal.timeout(500) });
                if (!res.ok) throw new Error("Network response was not ok");
                return await res.json();
            } catch (e) { 
                return previousData || { ax: 0, ay: 0, az: 1 }; 
            }
        }

        async function startCalibration() {
            initAudio(); // Required to unlock browser audio
            switchScreen('calibrating');
            let count = 3;
            document.getElementById('countdown-text').innerText = count;
            playTone(440, 'square', 0.2, 0.1); // Sound for "3"
            
            const iv = setInterval(async () => {
                count--;
                if (count > 0) {
                    document.getElementById('countdown-text').innerText = count;
                    playTone(440, 'square', 0.2, 0.1); // Sound for "2" and "1"
                } else { 
                    clearInterval(iv); 
                    baseline = await fetchIMU(); 
                    previousData = baseline; 
                    playTone(880, 'square', 0.5, 0.15); // Higher tone for "START"
                    startGame(); 
                }
            }, 1000);
        }

        function startGame() {
            switchScreen('game'); 
            isPlaying = true; 
            timeLeft = 30; 
            currentScore = maxScore;
            
            // FIX: Reset the UI text properly on the second try
            liveScoreText.innerText = currentScore;
            timerText.innerText = timeLeft;
            bubble.style.left = '50%';
            bubble.style.top = '50%';

            playBGM(); // Start the background music

            gameLoopInterval = setInterval(() => { 
                timeLeft--; 
                timerText.innerText = timeLeft; 
                if (timeLeft <= 0) endGame(); 
            }, 1000);
            imuInterval = setInterval(processIMU, 100);
        }

        async function processIMU() {
            if (!isPlaying) return;
            const data = await fetchIMU();
            if (!baseline || !previousData) { baseline = data; previousData = data; }
            
            const moveX = data.ax - previousData.ax, moveY = data.ay - previousData.ay, moveZ = data.az - previousData.az;
            const movement = Math.sqrt(moveX*moveX + moveY*moveY + moveZ*moveZ);
            
            if (movement > 0.05) {
                currentScore = Math.max(0, currentScore - Math.floor(movement * 250));
                liveScoreText.innerText = currentScore;
            }
            
            previousData = data;
            
            const absX = data.ax - baseline.ax;
            const absY = data.ay - baseline.ay;
            
            let xPos = Math.max(5, Math.min(95, 50 + (absX / 0.6) * 50));
            let yPos = Math.max(5, Math.min(95, 50 + (absY / 0.6) * 50));
            bubble.style.left = `${xPos}%`; bubble.style.top = `${yPos}%`;
        }

        function endGame() {
            isPlaying = false; 
            clearInterval(gameLoopInterval); 
            clearInterval(imuInterval);
            
            stopBGM(); // Stop music
            playTone(150, 'sawtooth', 0.8, 0.2); // Low buzzer sound for Game Over
            
            document.getElementById('final-score').innerText = currentScore;
            const b = document.getElementById('performance-badge');
            if (currentScore > 9000) { b.innerText = "Master"; b.className = "px-4 py-1 rounded-full text-sm font-bold bg-purple-900/50 text-purple-300 border border-purple-500"; }
            else if (currentScore > 5000) { b.innerText = "Good"; b.className = "px-4 py-1 rounded-full text-sm font-bold bg-blue-900/50 text-blue-300 border border-blue-500"; }
            else { b.innerText = "Needs Practice"; b.className = "px-4 py-1 rounded-full text-sm font-bold bg-red-900/50 text-red-300 border border-red-500"; }
            switchScreen('results');
        }
        function resetGame() { switchScreen('home'); }
    </script>
</body>
</html>"""

# ==========================================
# MPU6886 ACCELEROMETER DRIVER
# ==========================================
class MPU6886:
    def __init__(self, i2c):
        self.i2c = i2c
        self.addr = 0x68
        
        # FIX: Increased alpha from 0.15 to 0.6. 
        # This makes the filter settle significantly faster, eliminating the 
        # "ghost movement tail" that kept deducting points after a shake ends.
        self.alpha = 0.6 
        
        self.filtered_ax = 0.0
        self.filtered_ay = 0.0
        self.filtered_az = 1.0

        try:
            self.i2c.writeto_mem(self.addr, 0x6B, b'\x00')
            time.sleep_ms(10)
            self.i2c.writeto_mem(self.addr, 0x1C, b'\x10')
            self.connected = True
        except OSError:
            self.connected = False
            print("MPU6886 not found. Running in simulation mode.")

    def get_accel(self):
        if not self.connected:
            return 0.0, 0.0, 1.0 
            
        try:
            data = self.i2c.readfrom_mem(self.addr, 0x3B, 6)
            def to_signed(msb, lsb):
                val = (msb << 8) | lsb
                return val if val < 32768 else val - 65536
                
            raw_ax = to_signed(data[0], data[1]) / 4096.0
            raw_ay = to_signed(data[2], data[3]) / 4096.0
            raw_az = to_signed(data[4], data[5]) / 4096.0

            self.filtered_ax = (self.alpha * raw_ax) + ((1.0 - self.alpha) * self.filtered_ax)
            self.filtered_ay = (self.alpha * raw_ay) + ((1.0 - self.alpha) * self.filtered_ay)
            self.filtered_az = (self.alpha * raw_az) + ((1.0 - self.alpha) * self.filtered_az)

            return self.filtered_ax, self.filtered_ay, self.filtered_az
            
        except OSError:
            return 0.0, 0.0, 1.0

# ==========================================
# SYSTEM SETUP
# ==========================================
def setup_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    for ssid, password in NETWORKS:
        print(f"Trying to connect to: {ssid}")
        wlan.connect(ssid, password)
        
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            timeout -= 1
            time.sleep(1)
            
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            print(f"Connected successfully! Network config: {wlan.ifconfig()}")
            return ip
            
    print("Failed to connect to any network.")
    return "0.0.0.0"

def main():
    power_hold = machine.Pin(4, machine.Pin.OUT)
    power_hold.value(1)

    backlight = machine.Pin(27, machine.Pin.OUT)
    backlight.value(1)

    i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)
    imu = MPU6886(i2c)

    ip_address = setup_wifi()
    
    if ip_address == "0.0.0.0":
        print("Flag 0.0.0.0: Offline. Connect to a PC to debug Wi-Fi credentials.")
    else:
        print(f"Open this IP in your phone browser: http://{ip_address}")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(5)
    print("Server is running...")

    while True:
        try:
            conn, addr = s.accept()
            request = conn.recv(1024).decode('utf-8')
            
            if not request:
                conn.close()
                continue
                
            if 'GET /data' in request:
                ax, ay, az = imu.get_accel()
                response_data = json.dumps({"ax": ax, "ay": ay, "az": az})
                
                conn.send('HTTP/1.1 200 OK\n'.encode('utf-8'))
                conn.send('Content-Type: application/json\n'.encode('utf-8'))
                conn.send('Access-Control-Allow-Origin: *\n'.encode('utf-8'))
                conn.send('Connection: close\n\n'.encode('utf-8'))
                conn.send(response_data.encode('utf-8'))
                
            else:
                conn.send('HTTP/1.1 200 OK\n'.encode('utf-8'))
                conn.send('Content-Type: text/html\n'.encode('utf-8'))
                conn.send('Connection: close\n\n'.encode('utf-8'))
                conn.sendall(HTML_PAGE.encode('utf-8'))
                
            conn.close()
            gc.collect()
            
        except Exception as e:
            print("Error handling request:", e)

if __name__ == '__main__':
    main()