import tkinter as tk
from tkinter import PhotoImage
import keyboard
from PIL import Image, ImageTk
import pyaudio
import threading
from openai import OpenAI
import wave
import io
import json
import os
from dotenv import load_dotenv
import wave
import pyaudio
import mss
import base64
from io import BytesIO
import re
import matplotlib.pyplot as plt
import pyautogui
import replicate

# Load environment variables
load_dotenv()

# Audio recording settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

client = OpenAI()

class ChatbotApp:
    def __init__(self, root): #create a new tab called junin
        self.root = root
        self.root.title("JUNIN")
        self.root.configure(bg='white')
        
        # Load saved settings
        self.settings_file = "settings.json"
        self.settings = self.load_settings()
        
        # Remove overrideredirect to restore taskbar icon
        # self.root.overrideredirect(True)

        # Add checkbox for "Always on Top"
        self.always_on_top_var = tk.BooleanVar(value=self.settings.get("always_on_top", True))
        self.always_on_top_checkbox = tk.Checkbutton(root, text="Always on Top", variable=self.always_on_top_var, command=self.toggle_always_on_top)
        self.always_on_top_checkbox.pack(pady=5)
        self.root.attributes('-topmost', self.always_on_top_var.get())

        # Load and display the image
        script_dir = os.path.dirname(__file__)
        image_path = os.path.join(script_dir, "junin.png")
        image = Image.open(image_path)
        image.thumbnail((400, 400), Image.LANCZOS)
        self.root.geometry(f"{image.width + 50}x{image.height + 450}+100+100")
        self.photo = ImageTk.PhotoImage(image)
        self.label = tk.Label(root, image=self.photo, bg='white')
        self.label.pack(side="top", pady=10)

        # Chat display area
        self.chat_display = tk.Text(root, height=10, width=50, state='disabled', wrap='word', bg='lightgrey')
        self.chat_display.pack(pady=10)

        # User input area
        self.user_input = tk.Entry(root, width=50)
        self.user_input.pack(pady=5)
        self.user_input.bind("<Return>", self.send_message)

        # Voice record button
        self.record_button = tk.Button(root, text="Click to Record", command=self.toggle_recording, bg='blue', fg='white')
        self.record_button.pack(pady=5)
        # Register global hotkey for recording
        keyboard.add_hotkey('ctrl+alt', self.toggle_recording)

        # Hear response checkbox
        self.hear_response_var = tk.BooleanVar(value=self.settings.get("hear_response", False))
        self.hear_response_checkbox = tk.Checkbutton(root, text="Hear the response", variable=self.hear_response_var)
        self.hear_response_checkbox.pack(pady=5)

        # Voice selection dropdown
        self.voice_var = tk.StringVar(value=self.settings.get("selected_voice", "alloy"))
        self.voice_label = tk.Label(root, text="Select Voice:")
        self.voice_label.pack(pady=5)
        self.voice_dropdown = tk.OptionMenu(root, self.voice_var, "alloy", "echo", "fable", "onyx", "nova", "shimmer")
        self.voice_dropdown.pack(pady=5, padx=10)

        # PyAudio setup
        self.p = pyaudio.PyAudio()
        self.audio_stream = None
        self.is_recording = False
        self.chat_history = []

        # Save settings on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as file:
                return json.load(file)
        return {}

    def save_settings(self):
        self.settings["selected_voice"] = self.voice_var.get()
        self.settings["always_on_top"] = self.always_on_top_var.get()
        self.settings["hear_response"] = self.hear_response_var.get()
        with open(self.settings_file, 'w') as file:
            json.dump(self.settings, file)

    def toggle_always_on_top(self):
        self.root.attributes('-topmost', self.always_on_top_var.get())

    def toggle_recording(self, event=None):
        if self.is_recording:
            self.stop_recording()
            self.record_button.config(text="Click to Record", bg='blue')
        else:
            self.is_recording = True
            self.record_button.config(text="Recording...", bg='red')
            self.start_recording()

    def start_recording(self):
        self.frames = []
        self.audio_stream = self.p.open(format=FORMAT,
                                        channels=CHANNELS,
                                        rate=RATE,
                                        input=True,
                                        frames_per_buffer=CHUNK)
        # Start a new thread to handle recording
        self.recording_thread = threading.Thread(target=self.record)
        self.recording_thread.start()

    def record(self):
        while self.is_recording:
            data = self.audio_stream.read(CHUNK)
            self.frames.append(data)

        # Stop the audio stream after recording ends
        self.audio_stream.stop_stream()
        self.audio_stream.close()

        # Convert recorded audio to bytes
        audio_data = b''.join(self.frames)
        audio_file = io.BytesIO()
        with wave.open(audio_file, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(audio_data)
        audio_file.name = "output.wav"

        # Use OpenAI's speech-to-text
        transcript = self.transcribe_audio(audio_file)
        print("Transcrição", transcript)
        if transcript:
            self.display_message("You: " + transcript)
            response = self.get_response(transcript)
            self.display_message("Bot: " + response)
            if self.hear_response_var.get():
                self.speak_response(response)

    def stop_recording(self):
        self.is_recording = False

    def transcribe_audio(self, audio_file):
        try:
            audio_file.seek(0)  # Ensure the file pointer is at the start
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            return response.text
        except Exception as e:
            print("Error during transcription:", e)
            return ""   

    def get_chat_history(self):
        return "\n".join(self.chat_history)

    def get_response(self, user_message):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={ "type": "json_object" },
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are a helpful assistant.
                        Your answer must ALWAYS be a JSON object.

                    Format:
                    {
                        "type": "normal",
                        "content": "The response to the user"
                    }
                        """
                    },
                    {"role": "assistant", "content": self.get_chat_history()},
                    {"role": "user", "content": user_message}
                    ]
            )


            json_response = json.loads(response.choices[0].message.content)
            if json_response.get('type') == 'normal':
                return json_response.get('content')
            else:
                return "I'm sorry, I couldn't process that."

        except Exception as e:
            return f"Sorry, I couldn't get a response. Please try again later. Error: {e}"

    def speak_response(self, response_text):
        try:
            selected_voice = self.voice_var.get()
            response = client.audio.speech.create(
                model="tts-1",
                voice=selected_voice,
                input=response_text,
                response_format="wav"
            )
            audio_data = response.content
            audio_file = io.BytesIO(audio_data)
            audio_file.seek(0)

            # Play the WAV audio using PyAudio
            wf = wave.open(audio_file, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            data = wf.readframes(CHUNK)
            while data:
                stream.write(data)
                data = wf.readframes(CHUNK)

            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            print("Error during text-to-speech:", e)

    def display_message(self, message):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, message + "\n")
        self.chat_history.append(message)
        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END)

    def send_message(self, event=None):
        user_message = self.user_input.get().strip()
        if user_message:
            self.display_message("You: " + user_message)
            self.user_input.delete(0, tk.END)
            response = self.get_response(user_message)
            self.display_message("Bot: " + response)
            if self.hear_response_var.get():
                self.speak_response(response)

    def on_closing(self):
        keyboard.unhook_all_hotkeys()
        self.save_settings()
        self.root.destroy()
        
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatbotApp(root)
    root.mainloop()