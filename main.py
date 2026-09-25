import tkinter as tk
import threading
import queue
import pyaudiowpatch as pyaudio
import json
import audioop
from vosk import Model, KaldiRecognizer
import textwrap

class CaptionManager:
    """Manages the caption lines, wrapping them to fit the UI and applying FIFO clearing.
    
    This ensures that lines don't run off the screen or jump visual locations too often.
    """
    
    def __init__(self, max_lines=4, line_width=55):
        """Initialize the caption manager.
        
        Using a fixed line width rather than relying on GUI wrap allows us to manage
        precisely how many lines are currently visible on the screen.
        """
        self.max_lines = max_lines
        self.line_width = line_width
        self.finalized_lines = []
        self.current_partial = ""

    def handle_message(self, msg_type, text):
        """Processes a new queue message and returns the formatted text to display.
        
        We handle 'info', 'partial', and 'final' messages differently. Info messages reset
        the history, partials update the active draft, and final messages commit new lines.
        """
        if msg_type == "info":
            # Status messages override everything and reset state to clear old contexts.
            self.finalized_lines = []
            self.current_partial = ""
            return text
        elif msg_type == "final":
            if text.strip():
                # Split finalized text into wrapped segments so we can count lines accurately.
                new_lines = textwrap.wrap(text, width=self.line_width)
                self.finalized_lines.extend(new_lines)
                
                # Apply FIFO clearing: "only clear the first 2 lines and the 3-4lines will replace the 1-2 line"
                while len(self.finalized_lines) > self.max_lines:
                    self.finalized_lines = self.finalized_lines[2:]
            self.current_partial = ""
        elif msg_type == "partial":
            self.current_partial = text
            
        return self.get_display_text()

    def get_display_text(self):
        """Returns the current formatted caption text block for the canvas.
        
        Combines committed lines with the current active partial draft, shifting both if
        the total exceeds maximum lines. Shifting by blocks of 2 lines maintains stability.
        """
        if self.current_partial.strip():
            partial_lines = textwrap.wrap(self.current_partial, width=self.line_width)
        else:
            partial_lines = []
            
        combined_lines = self.finalized_lines + partial_lines
        
        # Apply FIFO shift to combined display lines as well to prevent UI overflow.
        display_lines = list(combined_lines)
        while len(display_lines) > self.max_lines:
            display_lines = display_lines[2:]
            
        return "\n".join(display_lines)

text_queue = queue.Queue()

def update_ui(canvas, text_id, shadow_ids, new_text):
    canvas.itemconfig(text_id, text=new_text)
    for sid in shadow_ids:
        canvas.itemconfig(sid, text=new_text)
    
def check_queue(root, canvas, text_id, shadow_ids, manager):
    try:
        msg_type, text = text_queue.get_nowait()
        new_text = manager.handle_message(msg_type, text)
        update_ui(canvas, text_id, shadow_ids, new_text)
    except queue.Empty:
        pass
    root.after(50, check_queue, root, canvas, text_id, shadow_ids, manager)

def audio_thread_worker():
    text_queue.put(("info", "Initializing Vosk Model (may take a moment to download)..."))
    try:
        # Vosk automatically downloads the model if it's missing
        model = Model(lang="en-us")
    except Exception as e:
        text_queue.put(("info", f"Model error: {e}"))
        return

    with pyaudio.PyAudio() as p:
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            
            if not default_speakers["isLoopbackDevice"]:
                for loopback in p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        default_speakers = loopback
                        break
                else:
                    text_queue.put(("info", "Error: Default loopback device not found."))
                    return
        except Exception as e:
            text_queue.put(("info", f"Audio init error: {e}"))
            return
            
        try:
            sample_rate = int(default_speakers["defaultSampleRate"])
            channels = default_speakers["maxInputChannels"]
            
            stream = p.open(format=pyaudio.paInt16,
                            channels=channels,
                            rate=sample_rate,
                            frames_per_buffer=4000,
                            input=True,
                            input_device_index=default_speakers["index"])
        except Exception as e:
            text_queue.put(("info", f"Stream error: {e}"))
            return

        text_queue.put(("info", "Listening to system audio..."))
        
        recognizer = KaldiRecognizer(model, sample_rate)
        
        while True:
            try:
                # WASAPI blocking fix: check if data is available
                if stream.get_read_available() > 0:
                    data = stream.read(4000, exception_on_overflow=False)
                    
                    # Convert stereo to mono for Vosk
                    if channels == 2:
                        data = audioop.tomono(data, 2, 1, 1)

                    if recognizer.AcceptWaveform(data):
                        res = json.loads(recognizer.Result())
                        if res.get("text", ""):
                            text_queue.put(("final", res["text"]))
                    else:
                        res = json.loads(recognizer.PartialResult())
                        if res.get("partial", ""):
                            text_queue.put(("partial", res["partial"]))
                else:
                    import time
                    time.sleep(0.01)
                    
            except Exception as e:
                text_queue.put(("info", f"Unexpected error: {e}"))
                import time
                time.sleep(1)

def main():
    root = tk.Tk()
    root.attributes('-transparentcolor', 'magenta')
    root.attributes('-topmost', True)
    root.overrideredirect(True)
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    width = 800
    height = 200
    x = (screen_width // 2) - (width // 2)
    y = screen_height - height - 100
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    canvas = tk.Canvas(root, width=width, height=height, bg='magenta', highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    
    font = ("Arial", 18, "bold")
    x_pos = width // 2
    y_pos = height // 2
    
    offsets = [(2,2), (-2,-2), (2,-2), (-2,2), (0,2), (2,0), (0,-2), (-2,0), (3,3), (-3,-3)]
    shadow_ids = []
    for dx, dy in offsets:
        sid = canvas.create_text(x_pos+dx, y_pos+dy, text="", font=font, fill="black", justify=tk.CENTER, width=width-40)
        shadow_ids.append(sid)
        
    text_id = canvas.create_text(x_pos, y_pos, text="Starting...", font=font, fill="white", justify=tk.CENTER, width=width-40)
    manager = CaptionManager()
    root.after(50, check_queue, root, canvas, text_id, shadow_ids, manager)
    
    threading.Thread(target=audio_thread_worker, daemon=True).start()
    
    def start_move(event):
        root.x = event.x
        root.y = event.y

    def stop_move(event):
        root.x = None
        root.y = None

    def do_move(event):
        deltax = event.x - root.x
        deltay = event.y - root.y
        x = root.winfo_x() + deltax
        y = root.winfo_y() + deltay
        root.geometry(f"+{x}+{y}")

    canvas.bind("<ButtonPress-1>", start_move)
    canvas.bind("<ButtonRelease-1>", stop_move)
    canvas.bind("<B1-Motion>", do_move)
    
    root.bind("<Escape>", lambda e: root.destroy())

    close_btn = tk.Button(root, text="X", bg="red", fg="white", font=("Arial", 12, "bold"), bd=0, command=root.destroy)
    close_btn.place(x=width-40, y=10, width=30, height=30)
    
    root.mainloop()

if __name__ == "__main__":
    main()
