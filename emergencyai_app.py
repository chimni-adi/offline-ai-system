import sounddevice as sd
import queue, json, threading, time, subprocess
import tkinter as tk
import pyttsx3
from vosk import Model, KaldiRecognizer

# ----------------
# MIC & TIME SETTINGS
# ----------------
MIC_DEVICE_INDEX = 9
MAX_LISTEN_SECONDS = 6

# ----------------
# VOICE SPEECH
# ----------------
engine = pyttsx3.init()
engine.setProperty('rate', 150)

speech_queue = queue.Queue()

def speak(text):
    speech_queue.put(text)

# ----------------
# VOSK SETUP
# ----------------
MODEL_PATH = r"C:\Aditee\EmergencyAI\model_en"
model = Model(MODEL_PATH)

SAMPLE_RATE = 48000
recognizer = KaldiRecognizer(model, SAMPLE_RATE)

audio_queue = queue.Queue()
ui_queue = queue.Queue()

def callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_queue.put(indata.tobytes())

# ----------------
# GUI
app = tk.Tk()
app.title("Emergency AI Assistant")
app.geometry("900x560")
app.resizable(False, False)
app.configure(bg="#0B1020")

# Background gradient
bg_canvas = tk.Canvas(app, width=900, height=560, highlightthickness=0)
bg_canvas.place(x=0, y=0)

for i in range(560):
    r = int(10 + i * 0.05)
    g = int(16 + i * 0.05)
    b = int(32 + i * 0.2)
    color = f"#{r:02x}{g:02x}{b:02x}"
    bg_canvas.create_line(0, i, 900, i, fill=color)

# Top Bar
topbar = tk.Frame(app, bg="#0B1020", height=90)
topbar.place(x=0, y=0, width=900)

logo = tk.Label(topbar, text="Emergency AI", fg="white", bg="#0B1020", font=("Segoe UI", 24, "bold"))
logo.place(x=30, y=22)

subtitle = tk.Label(topbar, text="Offline assistant — fast, secure, and smart", fg="#B8C2D6", bg="#0B1020", font=("Segoe UI", 12))
subtitle.place(x=30, y=58)

# Main Card (glassy)
card = tk.Frame(app, bg="#141A30", bd=0)
card.place(x=70, y=110, width=760, height=420)

card_canvas = tk.Canvas(card, bg="#141A30", highlightthickness=0)
card_canvas.place(x=0, y=0, width=760, height=420)

for i in range(420):
    color = "#0F1525" if i < 210 else "#0B1020"
    card_canvas.create_line(0, i, 760, i, fill=color)

status_circle = tk.Canvas(card, width=22, height=22, bg="#141A30", highlightthickness=0)
status_circle.place(x=40, y=25)
status_circle.create_oval(2, 2, 20, 20, fill="#34D399")

status_label = tk.Label(card, text="Status: Waiting", fg="#C9D4E6", bg="#141A30", font=("Segoe UI", 12))
status_label.place(x=75, y=22)

result_box = tk.Text(card, bg="#0B1226", fg="white", font=("Segoe UI", 13), wrap="word", bd=0, padx=15, pady=15)
result_box.place(x=40, y=70, width=680, height=230)
result_box.insert(tk.END, "🔊 Press START and speak your emergency...\n")
result_box.config(state="disabled")

divider = tk.Frame(card, bg="#1B2335", height=2)
divider.place(x=40, y=310, width=680)

glow_frame = tk.Frame(card, bg="#141A30", bd=0)
glow_frame.place(x=300, y=330, width=200, height=70)

mic_button = tk.Button(glow_frame, text="START", font=("Segoe UI", 14, "bold"), bg="#1F6FEB", fg="white", bd=0, relief="raised")
mic_button.place(x=30, y=10, width=140, height=50)

footer = tk.Label(card, text="Tip: Speak clearly. Keep sentences short.", fg="#9AA7BF", bg="#141A30", font=("Segoe UI", 11))
footer.place(x=40, y=375)

glow_on = False
glow_value = 0
glow_direction = 1

def glow_animation():
    global glow_value, glow_direction
    if not glow_on:
        glow_frame.config(bg="#141A30")
        return

    glow_value += glow_direction * 2
    if glow_value >= 40:
        glow_direction = -1
    elif glow_value <= 0:
        glow_direction = 1

    color = f"#{int(40 + glow_value):02x}{int(140 + glow_value):02x}{int(255):02x}"
    glow_frame.config(bg=color)
    app.after(40, glow_animation)

def set_glow(state):
    global glow_on, glow_value, glow_direction
    glow_on = state
    glow_value = 0
    glow_direction = 1
    glow_animation()

# ----------------
# LLM CALL
def call_ollama(prompt_text):
    model_name = "llama3"
    cmd = ["ollama", "run", model_name]

    result = subprocess.run(
        cmd,
        input=prompt_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120
    )

    return result.stdout.strip() or "No response."

# ----------------
# Listening & responding
def listen_thread():
    ui_queue.put(("clear", None))   # <-- CLEAR before each new query
    ui_queue.put(("status", "Listening..."))
    ui_queue.put(("circle", "#F59E0B"))
    ui_queue.put(("log", "Listening...\n"))
    set_glow(True)

    speak("Emergency assistant activated. Speak now.")
    start_time = time.time()
    text_detected = ""

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            device=MIC_DEVICE_INDEX,
            callback=callback
        ):
            while True:
                if time.time() - start_time > MAX_LISTEN_SECONDS:
                    break

                if not audio_queue.empty():
                    data = audio_queue.get()
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text_detected = result.get("text", "").lower()
                        if text_detected.strip():
                            break

    except Exception as e:
        ui_queue.put(("log", f"Audio error: {e}\n"))
        ui_queue.put(("status", "Error"))
        ui_queue.put(("circle", "#EF4444"))
        ui_queue.put(("button", "normal"))
        set_glow(False)
        return

    if not text_detected:
        ui_queue.put(("log", "No speech detected.\n"))
        ui_queue.put(("status", "Done"))
        ui_queue.put(("circle", "#34D399"))
        ui_queue.put(("button", "normal"))
        set_glow(False)
        return

    ui_queue.put(("log", f"You said: {text_detected}\n"))
    ui_queue.put(("status", "Processing..."))
    ui_queue.put(("circle", "#60A5FA"))

    try:
        response = call_ollama(text_detected)
    except subprocess.TimeoutExpired:
        response = "Assistant timed out. Try again."

    ui_queue.put(("log", f"Assistant: {response}\n"))
    ui_queue.put(("status", "Done"))
    ui_queue.put(("circle", "#34D399"))
    ui_queue.put(("button", "normal"))
    set_glow(False)

    speak(response)

def start_listening():
    mic_button.config(state="disabled")
    threading.Thread(target=listen_thread).start()

mic_button.config(command=start_listening)

# ----------------
# UI queue handler + Speech queue handler
def process_ui_queue():
    while not ui_queue.empty():
        action, value = ui_queue.get()

        if action == "status":
            status_label.config(text=f"Status: {value}")
        elif action == "log":
            result_box.config(state="normal")
            result_box.insert(tk.END, value)
            result_box.config(state="disabled")
            result_box.see(tk.END)
        elif action == "clear":
            result_box.config(state="normal")
            result_box.delete("1.0", tk.END)
            result_box.config(state="disabled")
        elif action == "circle":
            status_circle.delete("all")
            status_circle.create_oval(2, 2, 20, 20, fill=value)
        elif action == "button":
            mic_button.config(state=value)

    # Speak text from queue on main thread
    while not speech_queue.empty():
        text = speech_queue.get()
        engine.say(text)
        engine.runAndWait()

    app.after(100, process_ui_queue)

app.after(100, process_ui_queue)
app.mainloop()
