import pyaudiowpatch as pyaudio
import speech_recognition as sr

p = pyaudio.PyAudio()
wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
for loopback in p.get_loopback_device_info_generator():
    if default_speakers["name"] in loopback["name"]:
        default_speakers = loopback
        break

print(f"Using {default_speakers['name']}")

# Create stream manually
stream = p.open(format=pyaudio.paInt16,
                channels=default_speakers["maxInputChannels"],
                rate=int(default_speakers["defaultSampleRate"]),
                frames_per_buffer=1024,
                input=True,
                input_device_index=default_speakers["index"])

frames = []
print("Recording 5 seconds...")
for i in range(0, int(int(default_speakers["defaultSampleRate"]) / 1024 * 5)):
    data = stream.read(1024)
    frames.append(data)
print("Finished recording.")

stream.stop_stream()
stream.close()
p.terminate()

frame_data = b''.join(frames)
print(f"Captured {len(frame_data)} bytes.")

# Convert stereo to mono by taking every other sample (if 16-bit stereo)
if default_speakers["maxInputChannels"] == 2:
    print("Converting stereo to mono...")
    # 16-bit = 2 bytes. Stereo = 4 bytes per frame. We want 2 bytes per frame.
    mono_frames = bytearray()
    for i in range(0, len(frame_data), 4):
        mono_frames.extend(frame_data[i:i+2])
    frame_data = bytes(mono_frames)

audio_data = sr.AudioData(frame_data, int(default_speakers["defaultSampleRate"]), 2)

recognizer = sr.Recognizer()
try:
    print("Transcribing...")
    text = recognizer.recognize_google(audio_data)
    print("Text:", text)
except Exception as e:
    print("Error:", type(e), e)
