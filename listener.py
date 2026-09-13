import numpy as np
import sounddevice as sd
import queue
import threading
from faster_whisper import WhisperModel

MODEL_SIZE = "base.en"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"

model = None
audio_queue = queue.Queue()
stream = None
is_listening = False

def load_model():
    global model
    if model is None:
        print(f"Loading faster-whisper model: {MODEL_SIZE} on {DEVICE}...")
        model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("Model loaded.")
    return model

def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    audio_queue.put(bytes(indata))

def listen():
    global stream, is_listening
    
    load_model()
    
    try:
        print("Listening...")
        is_listening = True
        
        with sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=audio_callback
        ):
            audio_data = bytearray()
            silence_threshold = 0.01
            silence_duration = 0
            max_silence = 30
            
            while is_listening:
                try:
                    chunk = audio_queue.get(timeout=0.5)
                    audio_data.extend(chunk)
                    
                    audio_np = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    volume = np.abs(audio_np).mean()
                    
                    if volume < silence_threshold:
                        silence_duration += 1
                    else:
                        silence_duration = 0
                    
                    if silence_duration >= max_silence and len(audio_data) > 16000:
                        break
                        
                except queue.Empty:
                    continue
        
        if len(audio_data) < 1600:
            return ""
        
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        segments, info = model.transcribe(
            audio_np,
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        text = " ".join([seg.text for seg in segments]).strip()
        
        if text:
            print("Recognized:", text)
            return text.lower()
        
        return ""
        
    except Exception as e:
        print("Listen Error:", e)
        return ""