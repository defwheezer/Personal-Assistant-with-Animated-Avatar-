# To supress all the ALSA messages, import sounddevice first
import sounddevice as sd
import soundfile as sf

import os
import time
import asyncio
import wave
import random
import traceback
import re

import numpy as np
import pyaudio
import sox

import pygame
from pygame.locals import *
from pyvidplayer2 import Video

import speech_recognition as sr

import subprocess
from datetime import datetime
from pathlib import Path

from pydub import AudioSegment, effects

from gpiozero import LED, Button, MotionSensor, Device
from gpiozero.pins.lgpio import LGPIOFactory

from aio_ld2410 import LD2410, ReportBasicStatus, TargetStatus

from mistralai.client import Mistral

from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

# tts
from piper.voice import PiperVoice

# --- CONFIGURATION CLASS ---
class ButlerConfig:
	def __init__(self):
		# Paths
		self.PIPER_DIR = "/home/pi/pygame/lib/python3.11/site-packages/piper/models/"
		self.BASE_DIR = "/home/pi/pygame"
		self.TEMP_DIR = os.path.join(self.BASE_DIR, "temp/butler/")
		self.IMG_DIR  = os.path.join(self.BASE_DIR, "images/butler/")
		self.VID_DIR  = os.path.join(self.BASE_DIR, "videos/butler/")
		
		# Ensure directories exist
		os.makedirs(self.TEMP_DIR, exist_ok=True)
		
		#microphone device ID
		self.mic_device_index = 1
		
		# Hardware Pins
		self.PIN_LED = 26
		self.PIN_BTN_CANCEL = 21
		self.PIN_MOTION = 24
		self.SERIAL_PORT = '/dev/ttyAMA0' # LD2410 Port

		# API Keys
		self.MISTRAL_KEY = "your_key_here"
		self.ELEVEN_KEY  = "your_key_here"
		self.VOICE_ID    = "agL69Vji082CshT65Tcy" # Butler Voice

		# Display Settings
		self.SCREEN_RES = (1100, 1900)
		self.TEXT_BOX_RECT = [60, 1700, 960, 250]
		self.HEAD_POS = (0, 0)
		self.VID_POS = (0, -80)

# --- MAIN ASSISTANT CLASS ---
class ButlerAssistant:
	def __init__(self):
		self.config = ButlerConfig()
		
		# 1. State Management
		self.is_present = False
		self.cancel_ai_response = False
		self.music_playing = False
		self.last_presence_time = time.time()
		self.old_hour = -1

		# 2. Pygame Setup
		# match frequency with piper/11 labs (22050)
		pygame.mixer.pre_init(22050, -16, 2, 2048)
		pygame.init()
		self.screen = pygame.display.set_mode(self.config.SCREEN_RES, pygame.FULLSCREEN)
		self.font_main = pygame.font.SysFont("Arial", 35, bold=True)
		pygame.mouse.set_visible(False)

		# 3. Load Assets
		# 3. Load Assets
		self.black_out = pygame.image.load(os.path.join(self.config.IMG_DIR, "black_out_full-screen.jpg"))
		self.mouth_assets = self._load_mouth_assets()
		self.vid_idle = Video(os.path.join(self.config.VID_DIR, "butler_12sec.mp4"))
		self.vid_idle.resize((1028, 1900))
		
		# Initialize the ElevenLabs client here
		self.elevenlabs_client = ElevenLabs(api_key=self.config.ELEVEN_KEY)
		
		# 4. Initialize Services
		self.recognizer = sr.Recognizer() #speech recognition
		self.recognizer.energy_threshold = 500  # Default sensitivity
		self.recognizer.dynamic_energy_threshold = True
		
		self.mistral_client = Mistral(api_key=self.config.MISTRAL_KEY)
		self._setup_hardware()

	def _setup_hardware(self):
		Device.pin_factory = LGPIOFactory()
		self.led = LED(self.config.PIN_LED)
		self.btn_cancel = Button(self.config.PIN_BTN_CANCEL, pull_up=False, bounce_time=0.2)
		self.btn_cancel.when_pressed = self.handle_interrupt

	def _load_mouth_assets(self):
		# Assuming images are named 1.jpg through 14.jpg
		# Organized as (Standard, Alt/Blink) pairs
		assets = []
		for i in range(1, 15, 2):
			img1 = pygame.image.load(os.path.join(self.config.IMG_DIR, f"butler_mouth{i}.jpg"))
			img2 = pygame.image.load(os.path.join(self.config.IMG_DIR, f"butler_mouth{i+1}.jpg"))
			assets.append((img1, img2))
		return assets

	def handle_interrupt(self):
		print("!! Interrupt Signal Received !!")
		self.cancel_ai_response = True

	# --- SENSOR & ENVIRONMENT ---
	async def query_serial(self):
		"""
		Asynchronously communicates with the LD2410 sensor.
		Returns a cleaned list of data strings or None if the device is busy.
		"""
		# The device path should be in your config (e.g., '/dev/ttyAMA0')
		try:
			async with LD2410(self.config.SERIAL_PORT) as device:
				# We only need the most recent report to keep the Butler responsive
				async for report in device.get_reports():
					# Extract the 'basic' report data
					return self._parse_report_to_list(report.basic)
		except Exception as e:
			print(f"Serial Port Error: {e}")
			return None

	def _parse_report_to_list(self, report) -> list:
		"""
		Internal helper to turn the LD2410 report object into a clean 
		list of strings, removing parentheses and unwanted characters.
		"""
		# Convert report object to string: "TargetStatus.MovingTarget(dist=40, energy=80...)"
		raw_str = str(report)
		
		# Clean up formatting characters in one go
		for char in "()<>":
			raw_str = raw_str.replace(char, "")
		
		# Split into individual data points
		items = raw_str.split(',')
		
		clean_data = []
		for item in items:
			item = item.strip()
			# Extract only the value after '=' or '.' 
			# e.g., "dist=40" becomes "40", "TargetStatus.Moving" becomes "Moving"
			if '=' in item:
				clean_data.append(item.split('=')[1])
			elif '.' in item:
				clean_data.append(item.split('.')[1])
			else:
				clean_data.append(item)
				
		return clean_data

	def decode_data(self,data_arr):
		return_arr = []
		for item in data_arr:
			if (item.count(':') == 1):
				#print("Found ':' in item ",item)
				pos = item.find(':') + 1
				item = item[pos:]
				#print("presence: ",item)
			elif(item.count('=') == 1):
				#print("Found '=' in item ",item)
				pos = (item.find('=')) + 1
				item = item[pos:]
				#print("data: ",item)
			else:
				pass
			return_arr.append(item.strip())
		return return_arr

	def poll_presence(self):
		"""
		Polls the LD2410 sensor and returns True if a human is detected.
		"""
		try:
			# 1. Get raw data from the serial device
			# We use asyncio.run because the LD2410 library is asynchronous
			raw_report = asyncio.run(self.query_serial())
			#print("raw_report: ",raw_report)
			if not raw_report:
				return False

			# 2. Extract specific values
			# We look for 'TargetStatus' and distance/energy levels
			data_arr = self.decode_data(raw_report)
			
			# Mapping based on LD2410 protocol:
			# 2 = Static/Stationary target, 3 = Moving target
			presence_type = int(data_arr[0]) 
			static_energy = int(data_arr[3]) 
			distance      = int(data_arr[5]) 

			# 3. Presence Logic
			# Adjust these thresholds (50 and 100) based on your room size
			is_detected = (presence_type in [2, 3]) and (distance <= 50 or static_energy <= 100)

			if is_detected:
				self.led.on()
				# Optional: print for debugging
				#print(f"Presence Detected: Type {presence_type}, Dist {distance}")
			else:
				self.led.off()

			return is_detected
		except (IndexError, ValueError, TypeError) as e:
			# Catch data parsing errors specifically
			print(f"Sensor Data Error: {e}")
			return False
		except Exception as e:
			# Catch unexpected hardware/serial issues
			print(f"Presence Polling Failed: {e}")
			return False
			
	def update_environment(self):
		self.is_present = self.poll_presence()
		now = datetime.now()
		curr_hour = int(now.strftime("%-I"))
		
		if curr_hour != self.old_hour:
			if 6 <= int(now.strftime("%H")) < 22:
				self.play_time()
			self.old_hour = curr_hour
		return now.strftime("%-I:%M %p")

	# --- TEXT & UI ---
	def draw_text(self, text, color, rect, font):
		text = text.strip()
		rect = pygame.Rect(rect)
		y = rect.top
		font_height = font.get_linesize()

		while text:
			i = 1
			while font.size(text[:i])[0] < rect.width and i < len(text):
				i += 1
			if i < len(text):
				last_space = text.rfind(" ", 0, i)
				if last_space != -1: i = last_space + 1
			
			line_surf = font.render(text[:i], True, color)
			self.screen.blit(line_surf, (rect.left, y))
			y += font_height + 2
			text = text[i:]

	# --- AUDIO PIPELINE ---
	def synth_2_mp3(self, text):
		"""
		Synthesizes text using ElevenLabs with a local Piper fallback.
		Returns the path to the resulting WAV file.
		"""
		print(f"Synthesizing: {text}")
		
		# Use Path objects to avoid string concatenation errors
		temp_dir = Path(self.config.TEMP_DIR)
		mp3_path = temp_dir / "11labs_temp.mp3"
		wav_path = temp_dir / "11labs_temp.wav"

		try:
			# 1. Attempt ElevenLabs Synthesis
			audio_stream = self.elevenlabs_client.text_to_speech.convert(
				voice_id="agL69Vji082CshT65Tcy", # Your Butler Voice
				output_format="mp3_22050_32",
				text=text,
				model_id="eleven_multilingual_v2",
				voice_settings=VoiceSettings(
					stability=0.4, # Increased slightly for more consistent speech
					similarity_boost=0.8,
					style=0.5,
					use_speaker_boost=True,
					speed=1.2
				),
			)

			# 2. Save the stream to file
			with open(mp3_path, "wb") as f:
				for chunk in audio_stream:
					if chunk:
						f.write(chunk)

			# 3. Convert MP3 to WAV (Required for your volume/lip-sync logic)
			self.convert_mp3_to_wav(mp3_path, wav_path)
			
			# 4. Apply Audio Effects (Normalization/Sox)
			processed_path = self.process_audio_normalization(wav_path)
			
			return processed_path

		except Exception as e:
			print(f"ElevenLabs Error: {e}. Falling back to local Piper TTS.")
			# If the API fails, use the local engine you already have set up
			return self.synth_local_piper(text)

	def convert_mp3_to_wav(self, src, dst):
		"""Converts MP3 to WAV using pydub."""
		try:
			sound = AudioSegment.from_mp3(src)
			sound.export(dst, format="wav")
		except Exception as e:
			print(f"Conversion Error: {e}")
			
	def process_audio_normalization(self, filepath, target_dbfs=-3.0):
		"""
		Reads a wav file, normalizes the volume to a target level,
		and saves it back to the same location.
		"""
		try:
			# 1. Load the audio file
			audio = AudioSegment.from_wav(filepath)
			
			# 2. Calculate how much to "turn up the volume" 
			# to hit our target (-3.0 dB is loud but safe from clipping)
			change_in_dbfs = target_dbfs - audio.max_dbfs
			
			# 3. Apply the gain
			normalized_audio = audio.apply_gain(change_in_dbfs)
			
			# 4. Export back to wav
			normalized_audio.export(filepath, format="wav")
			
			return filepath
			
		except Exception as e:
			print(f"Normalization failed: {e}")
			return filepath # Return the original if normalization fails

	def apply_voice_effects(self, filepath):
		output = filepath.replace(".wav", "_fx.wav")
		tfm = sox.Transformer()
		tfm.pitch(-4)
		tfm.bass(gain_db=15)
		tfm.build(filepath, output)
		return output

	def synth_local_piper(self, text):
		"""
		Local fallback TTS using Piper. 
		Uses a robust process management to ensure the file is written.
		"""
		# 1. Path Setup
		model = "en_US-hfc_male-medium.onnx"
		model_path = Path(self.config.PIPER_DIR) / model
		output_wav = Path(self.config.TEMP_DIR) / "piper_fallback.wav"

		# Debug: Check if model exists
		if not model_path.exists():
			print(f"PIPER ERROR: Model file not found at {model_path}")
			return None

		# 2. Command Construction
		# We use the absolute path to the piper executable if possible
		command = [
			"piper", 
			"--model", str(model_path), 
			"--output_file", str(output_wav)
		]

		try:
			# 3. Execution with explicit Close
			# Using .communicate() is better than .write() because it sends 
			# the text AND an EOF (End of File) signal immediately.
			process = subprocess.Popen(
				command,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				text=True  # Allows us to send strings instead of bytes
			)
			
			stdout, stderr = process.communicate(input=text)

			# 4. Success Check
			if process.returncode != 0:
				print(f"PIPER CRASHED: {stderr}")
				return None

			if output_wav.exists() and output_wav.stat().st_size > 0:
				print(f"Piper successfully generated: {output_wav.name}")
				return self.process_audio_normalization(str(output_wav))
			
			print("PIPER ERROR: Process finished but wav file is empty or missing.")
			return None

		except Exception as e:
			print(f"Piper Subprocess Failed: {e}")
			return None

	def speak_wav(self, filename, text2speak):
		print("filename: ",filename)
		CHUNK = 2048
		wf = wave.open(str(filename), 'rb')
		p = pyaudio.PyAudio()
		stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
						channels=wf.getnchannels(), rate=wf.getframerate(), output=True)

		data = wf.readframes(CHUNK)
		while data and not self.cancel_ai_response:
			stream.write(data)
			audio_data = np.frombuffer(data, dtype=np.int16)
			vol_idx = min(int(np.mean(np.abs(audio_data)) / 1000), 6)

			# Animation
			img = self.mouth_assets[vol_idx][random.choice([0, 1])]
			self.screen.blit(img, self.config.HEAD_POS)
			pygame.draw.rect(self.screen, (0,0,0), self.config.TEXT_BOX_RECT)
			self.draw_text(text2speak, (255, 255, 255), self.config.TEXT_BOX_RECT, self.font_main)
			pygame.display.update()
			data = wf.readframes(CHUNK)

		#end with mouth closed, eyes open
		img = self.mouth_assets[0][0]
		self.screen.blit(img, self.config.HEAD_POS)
		pygame.display.update()
		stream.stop_stream(); 
		stream.close(); 
		p.terminate()

	# --- BEHAVIOR LOOPS ---
	def listen_for_speech(self):
		with sr.Microphone(device_index = self.config.mic_device_index) as source:
			# draw the resting face
			img = self.mouth_assets[0][1]
			self.screen.blit(img, self.config.HEAD_POS)
			# draw text box
			pygame.draw.rect(self.screen, (0,0,0), self.config.TEXT_BOX_RECT)
			self.draw_text("Listening...", (100, 100, 255), self.config.TEXT_BOX_RECT, self.font_main)
			pygame.display.update()
			#self.recognizer.adjust_for_ambient_noise(source, duration=1)			
			try:
				pygame.draw.rect(self.screen, (0,0,0), self.config.TEXT_BOX_RECT)
				self.draw_text("...", (100, 100, 255), self.config.TEXT_BOX_RECT, self.font_main)
				pygame.display.update()
				audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
				return self.recognizer.recognize_google(audio)
			except: return "x o x"

	def handle_active_interaction(self):
		"""
		Handles the conversation flow using the Mistral v2 SDK.
		"""
		# turn on led to indicate presence
		self.led.on()
		self.last_presence_time = time.time()
		# 1. Get input from the user
		user_input = self.listen_for_speech()
		# dont print if no input 'x o x'
		if not user_input == "x o x":
			print("user_input: ",user_input)
		# "x o x" is our internal code for "no speech detected" or "error"
		if user_input == "x o x" or not user_input.strip():
			return

		try:
			# 2. Mistral v2 API Call
			# We use a simple list of dictionaries now
			messages = [
				{
					"role": "system",
					"content": "You also are a typical critical reddit commentor in a programming subreddit. You are a super intelligent.  Keep responses concise."
				},
				{
					"role": "system",
					"content": "Your name is Jarvis. My name is Bro",
				},
				{
					"role": "system",
					"content": "when answering, do not use periods with abbreviations and do not use dash.",
				},
				{
					"role": "user",
					"content": user_input
				}
			]

			# Note the change from .chat to .chat.complete
			chat_response = self.mistral_client.chat.complete(
				model="mistral-tiny",
				messages=messages
			)

			# Extract the text content from the response object
			response_text = chat_response.choices[0].message.content
			#remove 'thought' portion of response
			# FIRST asterisk of the paragraph and the LAST one.
			response_text = re.sub(r'\*.*?\*', '', response_text).strip()
			# remove 'Jarvis:' at start of response
			response_text = response_text.removeprefix("Jarvis:").strip()
			# Optional: Clean up double spaces left behind by the removal
			response_text = re.sub(r'\s+', ' ', response_text)
			print(f"Response  : {response_text}")

			# 3. Sentence-by-Sentence Processing
			# This allows the 'Cancel' button to work between sentences
			sentences = response_text.replace('!', '.').replace('?', '.').split('.')

			for sentence in sentences:
				# Check if the user pressed the 'Cancel' button while the Butler was mid-thought
				if self.cancel_ai_response:
					print("Speech interrupted by user.")
					break

				clean_sentence = sentence.strip()
				if len(clean_sentence) > 1:
					# Run the audio pipeline
					audio_file = self.synth_2_mp3(clean_sentence)

					# Speak and animate
					if audio_file:
						self.speak_wav(audio_file, clean_sentence)

			# Reset the interrupt flag for the next time someone walks in
			self.cancel_ai_response = False

		except Exception as e:
			print(f"Mistral API Error: {e}")
			traceback.print_exc()

	def handle_idle_state(self, time_str):
		"""The 'Waiting' behavior: Ambient animations and clock."""
		self.led.off()
		if self.music_playing:
			pygame.mixer.music.stop()
			self.music_playing = False

		idle_time = time.time() - self.last_presence_time
		
		if idle_time < 120:
			# Play swirl animation
			if not self.vid_idle.active:
				self.vid_idle.restart()
			if self.vid_idle.draw(self.screen, self.config.VID_POS):
				pygame.display.update()
		else:
			# Deep sleep: Black screen with time_label
			time_label = self.update_environment()
			self.screen.blit(self.black_out, (0, 0))
			self.draw_text(time_label, (150, 150, 150), [400, 900, 300, 100], self.font_main)
			pygame.display.update()

	def play_time(self):
		"""
		Synthesizes and speaks the current time in a natural, conversational format.
		"""
		now = datetime.now()
		hour = now.strftime("%-I")      # 12-hour format without leading zero
		minute_int = int(now.strftime("%M"))
		am_pm = now.strftime("%p")
		
		# 1. Format the minutes for natural speech
		if minute_int == 0:
			minute_speech = ""          # "It is 4" (Top of the hour)
		elif minute_int < 10:
			minute_speech = f" oh {minute_int}"  # "It is 4 oh 5"
		else:
			minute_speech = f" {minute_int}"     # "It is 4 15"

		# 2. Construct the final text
		# Note: We remove periods from A.M./P.M. for better TTS flow
		speak_text = f"It is {hour}{minute_speech} {am_pm.replace('.', '')}"
		
		print(f"Time Check: {speak_text}")

		try:
			# 3. Use ElevenLabs for high-quality time announcements
			temp_wav = self.synth_2_mp3(speak_text)
			print("ElevenLabs temp_wav: ",temp_wav)
			if temp_wav:
				# We call our refactored speak_wav from the previous step
				self.speak_wav(temp_wav, speak_text)
			else:
				# Fallback to local Piper TTS if ElevenLabs fails/limit reached
				print("ElevenLabs failed, attempting local fallback...")
				temp_wav = self.synth_local_piper(speak_text)
				print("Piper temp_wav generated: ",temp_wav)
				self.speak_wav(temp_wav, speak_text)
				
		except Exception as e:
			print(f"Failed to announce time: {e}")

	def run(self):
		"""The engine of the application."""
		print("Butler Assistant is online.")
		try:
			while True:
				time_label = self.update_environment()
				
				if self.is_present:
					self.handle_active_interaction()
				else:
					self.handle_idle_state(time_label)
				
				pygame.time.wait(16)
		except Exception:
			traceback.print_exc()
		finally:
			self.cleanup

	def cleanup(self):
		self.led.off()
		self.vid_idle.stop()
		pygame.quit()
		print("System shutdown.")

if __name__ == "__main__":
	butler = ButlerAssistant()
	butler.run()
