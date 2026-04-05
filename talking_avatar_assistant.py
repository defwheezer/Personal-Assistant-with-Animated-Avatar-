# To supress all the ALSA messages, import souddevice first
import sounddevice as sd
import soundfile as sf

import os
from os import path

# 11labs speech synth
from elevenlabs.client import ElevenLabs
from elevenlabs import play, save
from elevenlabs import VoiceSettings

# for error reporting
import traceback

#try multiprocessing for offloading sythesis and/or speech recognition (speech-2-txt)
#import multiprocessing

# analog-to-digital module ADS1115, use for presence detector
import board
import busio
from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

# GPIO Raspi 5
from gpiozero import Device, LED, MotionSensor, Button
from gpiozero.pins.lgpio import LGPIOFactory

import asyncio
from aio_ld2410 import LD2410, ReportBasicStatus, TargetStatus

# Importing the pygame module
import pygame
from pygame.locals import *
from pyvidplayer2 import Video

# to play audio in chunks (for volume extraction/lip-synch)
import pyaudio

# for audio maniputation (AudioSegment for chunks, effects for normalization of audio)
from pydub import AudioSegment, effects

#imports for real-time volume measure
import sox

import wave
import numpy as np
import time
from time import strftime
from datetime import datetime

# tts
from piper.voice import PiperVoice

# whisper speech recognition
import speech_recognition as sr

# general maths
import sys, math
import random

# Mistral chat
from mistralai.client import Mistral

# Mistral API key
# enter your api_key
mistral_api_key = "your api_key"
mistral_model = "mistral-large-latest"
mistral_client = Mistral(api_key=mistral_api_key)

# 11labs API key
# enter your api_key, aquire from https://elevenlabs.io/
client = ElevenLabs(
    api_key="your api_key"
)

# whisper model path
# download model from https://huggingface.co/dominguesm/whisper-tiny-pt and put in your local dir
model_path = "/home/pi/pygame/lib/python3.11/site-packages/whisper/tiny.en.pt"

print("initialize Recognizer")
r = sr.Recognizer()
r.energy_threshold = 4000  #use this to adjust for background noise triggering detection
r.timeout = 4 # timeout after 4 sec of silence
print("initialized")

# Create the I2C bus for ADS1115, make sure to enable i2c in raspi-config
i2c = board.I2C()
# Create the ADC object using the I2C bus
ads = ADS1115(i2c)
# Create single-ended input on channel 0, for 12-way switch (using resistor-ladder)
chan = AnalogIn(ads, ads1x15.Pin.A0)

# Set lgpio backend for Raspberry Pi 5
Device.pin_factory = LGPIOFactory()
led = LED(26)
button_select = Button(20,pull_up=False,bounce_time=0.2)
button_cancel = Button(21,pull_up=False,bounce_time=0.2)
presence_det = MotionSensor(24)

# piper command line test:
#echo "Text you want to speak" | piper --model /home/pi/pygame/lib/python3.11/site-packages/piper/en_US-hfc_male-medium.onnx --output_file output.wav

# piper tts setup
voicedir = "/home/pi/pygame/lib/python3.11/site-packages/piper/" #Where onnx model files are stored on pi5

# download voices of interest from https://huggingface.co/rhasspy/piper-voices/tree/main
# load voice model and voice for tts
# male models
model = voicedir+"en_US-hfc_male-medium.onnx"
# model = voicedir+"en_GB-semaine-medium.onnx"

# female models
# model = voicedir+"en_US-libritts_r-medium.onnx"

print ("voice loading...")
voice = PiperVoice.load(model)
print ("voice loaded")


presence = False
presence_det_current_time = int(time.time())
presence_det_start_time = int(time.time())
presence_det_total_time=0
#print("PIR_current_time: ",PIR_current_time, ", PIR_start_time: ",PIR_start_time)

HEIGHT = 1900 # screen HEIGHT
WIDTH = 1100 #screen WIDTH

# Define colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
philosophy_text = "this is test philosophy_text text!"

# Initiate pygame
pygame.mixer.pre_init(frequency=48000, buffer=2048)
pygame.mixer.init()

pygame.init()
pygame.font.init() # Initialize the font module
font_size = 40
font = pygame.font.SysFont('Arial', 30, italic=True)
font2 = pygame.font.SysFont('Arial', 50, bold=True)

# pygame.Rect(left, top, width, height)
text_box_rect = pygame.Rect(50, 1600, 900, 400)
text_surface = font.render(philosophy_text, True, WHITE)
text_rect = text_surface.get_rect()

# Create a display surface object
screen = pygame.display.set_mode((WIDTH, HEIGHT),pygame.FULLSCREEN)
#screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.draw.rect(screen, pygame.Color(RED), [50, 1400, 900, 400])
				
# Hide the mouse cursor initially
pygame.mouse.set_visible(False)

# Creating a new clock object to
clock = pygame.time.Clock()

# set framerate
clock.tick(60)

# set the position of the talking head on the screen
head_x = 10
head_y = 0

# set the position of the video on the screen
video_x = -25
video_y = -80

# wave file to speak
# use full path if outside this folder

file_path_temp = "/home/pi/pygame/temp/butler/"
file_path_images = "/home/pi/pygame/images/butler/"
file_path_sounds = "/home/pi/pygame/sounds/butler/"
file_path_videos = "/home/pi/pygame/videos/butler/"
# use these for pauses, etc.
silence_1sec = file_path_sounds + "silence_1sec.wav"
silence_2sec = file_path_sounds + "silence_2sec.wav"

print("Get image files...")
# create video object

vid_swirl = Video(file_path_videos + "butler_12sec.mp4")
# resize vid to fill screen
vid_swirl.resize((1200,2000))

black_out_shape = file_path_images + "black_out_full-screen.jpg"
black_out_half = file_path_images + "black_out_full-screen.jpg"

# speaking butler face
face1 = file_path_images + "butler_eyes_open.jpg"
face2 = file_path_images + "butler_eyes_closed.jpg"
face3 = file_path_images + "butler_mouth1.jpg"
face4 = file_path_images + "butler_mouth2.jpg"
face5 = file_path_images + "butler_mouth3.jpg"
face6 = file_path_images + "butler_mouth4.jpg"
face7 = file_path_images + "butler_mouth5.jpg"
face8 = file_path_images + "butler_mouth6.jpg"
face9 = file_path_images + "butler_mouth7.jpg"
face10 = file_path_images + "butler_mouth8.jpg"
face11 = file_path_images + "butler_mouth9.jpg"
face12 = file_path_images + "butler_mouth10.jpg"
face13 = file_path_images + "butler_mouth11.jpg"
face14 = file_path_images + "butler_mouth12.jpg"

print("Retrieved image files")

black_out = pygame.image.load(black_out_shape)

# resting face, eyes open
mouth1 = pygame.image.load(face1)
# resting face, eyes closed
mouth2 = pygame.image.load(face2)

# talking face
mouth3 = pygame.image.load(face3)
mouth4 = pygame.image.load(face4)
mouth5 = pygame.image.load(face5)
mouth6 = pygame.image.load(face6)
mouth7 = pygame.image.load(face7)
mouth8 = pygame.image.load(face8)
mouth9 = pygame.image.load(face9)
mouth10 = pygame.image.load(face10)
mouth11 = pygame.image.load(face11)
mouth12 = pygame.image.load(face12)
mouth13 = pygame.image.load(face13)
mouth14 = pygame.image.load(face14)

def synth_2_mp3(mytext):
# audio tags
# Emotions: [curious], [excited], [nervous], [sad], [angry]
# Delivery: [whispers], [shouts], [quietly], [loudly]
# Reactions: [laughs], [sighs], [gasps], [clears throat]
# must use model_id="eleven_v3",
	#text_with_tags = "[clears throat]" + mytext + "[laughs]"

	print("synthisize text: ",mytext)
	try:
		audio = client.text_to_speech.convert(
		#voice_id="AKGWkp89mKHLHYRQrjRX", female nurse
		#voice_id="E26x180kR5cxrsOoElJP", musashi
		voice_id="agL69Vji082CshT65Tcy",
		output_format="mp3_22050_32",
		text = mytext,
		model_id="eleven_multilingual_v2",
			# Optional voice settings that allow you to customize the output
			voice_settings=VoiceSettings(
				stability=0.0,
				similarity_boost=0.8,
				style=0.8,
				use_speaker_boost=True,
				speed=1.2,
			),
		)

		mp3_filename = "11labs_temp.mp3"
		full_path = "temp/" +mp3_filename
		print("mp3 synthisized as: ",mp3_filename)
		with open(full_path, "wb") as f:
			for chunk in audio:
				if chunk:
					f.write(chunk)
		print("saved as: ",full_path)
		# return just the file name, not full path!
		print("convert mp3 to wav: ",full_path)
		wav_filename = convert_mp3_to_wav(mp3_filename)
		if not wav_filename == None:
			print("process_wav: ",wav_filename)
			wav_filename = process_wav(wav_filename)
		print("synth_2_mp3 return file: ",wav_filename)
		return wav_filename
	except:
		print(f"An error occurred: {e}")
		print("error occured trying to get sythn voice from 11labs.")

def convert_mp3_to_wav(my_filename):
	# Convert MP3 to WAV
	src = "temp/11labs_temp.mp3"
	dst = "temp/11labs_temp.wav"
	try:
		sound = AudioSegment.from_mp3(src)
		sound.export(dst, format="wav")
		print(f"Successfully converted {src} to {dst}")
		speak_wav(dst,"")
	except Exception as e:
		print(f"An error occurred: {e}")
		print("Please ensure FFmpeg is installed and added to your system's PATH.")
	
def poll_presence():
	# this is for the presense detector, easier path if you just use simple PIR dwetector
	global presence
	try:
		LD2410_data = asyncio.run(query_serial())
		#print(LD2410_data)
	except:
		print("Error trying to run 'asyncio.run(query_serial())'")
		pass
	
	try:
		data_arr = decode_data(LD2410_data)
	except:
		print("Error trying to run 'decode_data(LD2410_data)'")	#print(data_arr)
		pass

	try:
		presence_data = int(data_arr[0]) # 2 or 3
		distance_data = int(data_arr[5]) # < 100 for presence
		static_data = int(data_arr[3]) # < 100 for presence
		if presence_data == 2 and (distance_data <=50 or static_data <=100):
			presence = True
			print("static energy detected")
			led.on()
		elif presence_data == 3 and (distance_data <=50 or static_data <=100):
			presence = True
			print("3 Motion detected")
			led.on()
		else:
			#print("presence_data: ",presence_data)
			presence = False
			led.off()
	except:
		print("Polling failed, no data in array")
		pass
		
async def query_serial():
	async with LD2410('/dev/ttyAMA0') as device:
		#async with device.configure():
			#ver = await device.get_firmware_version()
			#print(f'[+] Running with firmware v{ver}')
        # Reports are typically generated every 100ms.
		async for report in device.get_reports():
			formatted_report = extract_data(report.basic)
			#print(report.basic)
			return formatted_report

def extract_data(report) -> str:
	return_arr = []
	#print("processing report",report)
	str_report = str(report)
	str_report = str_report.replace('(', '')
	str_report = str_report.replace(')', '')
	str_report = str_report.replace('<', '')
	str_report = str_report.replace('>', '')
	items = str_report.split(',')
	for item in items:
		if (item.count("TargetStatus") == 1):
			item_arr = item.split(".")
			return_arr.append(item_arr[1].strip())
			#print(item_arr[1].strip())
		else:
			return_arr.append(item.strip())
			#print(item.strip())
	return return_arr
	
def decode_data(data_arr):
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
	
def on_button_cancel_pressed():
	print("Button_stop pressed!")
	global cancel_ai_response
	cancel_ai_response = True

# draw some text into an area of a surface
# automatically wraps words
# returns any text that didn't get blitted
def drawText(surface, text, color, rect, font, aa=False, bkg=None):
	#print("Draw text: ",text)
	# strip white space at eginning and end of string
	text = text.strip()
	rect = pygame.Rect(rect)
	y = rect.top
	#print("rect.top: ",rect.top, ", rect.bottom: ",rect.bottom, " rect.width: ",rect.width)
	lineSpacing = -2

	# get the height of the font
	fontHeight = font.size("Tg")[1]

	while text:
		i = 1

		# determine if the row of text will be outside our area
		if y + fontHeight > rect.bottom:
			break

		# determine maximum width of line
		while font.size(text[:i])[0] < rect.width and i < len(text):
			i += 1

		# if we've wrapped the text, then adjust the wrap to the last word
		if i < len(text):
			i = text.rfind(" ", 0, i) + 1

		# render the line and blit it to the surface
		if bkg:
			image = font.render(text[:i], 1, color, bkg)
			image.set_colorkey(bkg)
		else:
			image = font.render(text[:i], aa, color)

		surface.blit(image, (rect.left, y))
		y += fontHeight + lineSpacing

		# remove the text we just blitted
		text = text[i:]

	return text
	

def apply_sox(filename):
	# Define input and output file paths
	print("Start sox on file: ",filename)
	input_filepath = filename
	output_filepath = "temp/"+"time_effects.wav"
	print("Input file: ",input_filepath ,", output file: ",output_filepath)
	# Create a transformer object
	tfm = sox.Transformer()
	print("sox.Transformer made")
	# Shift the pitch up by 2 semitones (or -2 to shift down)
	semitones_to_shift = -4

	tfm.pitch(semitones_to_shift)
	#tfm.flanger()
	tfm.bass(gain_db=20)
	#tfm.echo(gain_in = 0.8, gain_out = 0.4, n_echos = 1,delays = [60],decays = [0.4])
	tfm.reverb(room_scale=10)
	#tfm.chorus(n_voices=2)

	# default reverb(reverberance: float = 50, high_freq_damping: float = 50, room_scale: float = 100, stereo_depth: float = 100, pre_delay: float = 0, wet_gain: float = 0, wet_only: bool = False)

	tfm.build(input_filepath, output_filepath)

	print(f"Reverbed audio saved to {output_filepath}")
	return output_filepath

def process_wav(src_file):
	# pydub effects
	input_file = src_file
	output_file = input_file
	#output_file = "temp/time_normalized.wav" # wav
	sound = AudioSegment.from_wav(input_file)
	sound = effects.normalize(sound)
	sound.export(output_file, format="wav")
	return output_file

def playTime():
	date = datetime.now()
	hour = date.strftime("%-I")
	minute = date.strftime("%-M")
	am_pm = date.strftime("%p")
	if am_pm == "AM":
		am_pm = "A M"
	else:
		am_pm = "P M"
	day = date.strftime("%d")    # Results in '23'
	month = date.strftime("%B")  # Results in 'October'
	year = date.strftime("%y")
	whole_date = date.strftime("%d/%m/%y")   # Results in '23/10/17'
	full_datetime = date.strftime("%d/%m/%y at %-H:%M%p") # Results in 23/10/17 at 09:20AM
	#if zero then skip, else if leading zero (01,02, etc) change '0' to 'oh':
	if int(minute) == 0:
		minute = " "
	elif int(minute) < 10:
		minute = " oh " + str(minute)
	#speakTime = "Today is " + month + " " + day + ". The current time is " + hour + " " + minute + " " + am_pm
	speakTime = "It is " + hour + " " + minute
	print("speakTime text: ",speakTime)
	print("try 11labs synth: ",speakTime)
	tempsynth = synth_2_mp3(speakTime)
	print("11labs file: ",tempsynth)
	if tempsynth == None:
		print("Pass")
	else:
		speak_wav(tempsynth, speakTime)
	
def playTxt(txt2speak):
	# use this if you just want to speak some text locally (using whisper)
	print("playTxt text: ",txt2speak)
	try:
		filename = file_path_temp+"temptxt"+".wav"
		print("file name made: ",filename)
		wav_file = wave.open(filename, 'w')
		wav_file.setnchannels(1)
		wav_file.setframerate(22050)
		wav_file.setsampwidth(2)
		print("wav_file opened")
	except:
		print("Something went wrong making wave file: ",filename)
	try:
		audio = voice.synthesize_wav(txt2speak, wav_file)
		print("audio file synthesized")
		wav_file.close()
		print(f"Audio saved to {filename}")
	except:
		print("Something went wrong synthesizing: ",txt2speak)
		wav_file.close()
	# apply effects
	#play wav file
	filename = apply_sox(filename)
	#filename = process_wav(filename)
	speak_wav(filename,txt2speak)
	
def speak_wav(toSpeak,txt):

	filename = toSpeak # wav file
	text2speak = txt # string of text
	
	# Configuration
	CHUNK = 2048   # Number of frames per buffer
	#CHUNK = 512   # Number of frames per buffer, higher numer = longer latency - use this one for windows
	#CHUNK = 1024  # Number of frames per buffer
	try:
		#print("Try to open: ",filename)
		wf = wave.open(filename, 'rb')

		#print("Initialize PyAudio...")
		# Initialize PyAudio
		p = pyaudio.PyAudio()

		#print("Open a streaming play back...")
		# Open a streaming play back
		stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
						channels=wf.getnchannels(),
						rate=wf.getframerate(),
						output=True)

		#print(f"Playing '{filename}' and monitoring levels...")
		
		previous_sound_vol = 0
		
		# Read data in chunks
		data = wf.readframes(CHUNK)
		while data:
			# Play the audio chunk
			stream.write(data)

			# Process the data to get the audio level
			# Convert byte data to numpy array
			audio_data = np.frombuffer(data, dtype=np.int16) # assuming 16-bit WAV

			# Calculate the average amplitude (absolute mean) as the "level"
			# A higher average indicates a louder sound
			level = np.mean(np.abs(audio_data))

			# You can also calculate RMS for a more standard loudness measure:
			# rms = np.sqrt(np.mean(audio_data**2))

			#print("Current Level (Avg Amplitude): ", int(level/1000))

			# Read next chunk
			data = wf.readframes(CHUNK)
			
			#print("sound_vol: ",sound_vol)
			blink = 0 # initialize var
			randnum = random.randrange(0,20)
			if randnum >= 15:
				blink = 1
			else:
				blink = 0
			sound_vol = int(level/1000)	
			if sound_vol >= 7:
				sound_vol = 6
			# mouth shapes 3-13
			match sound_vol:
				case 0:
					if blink:
						image = mouth2
					else:
						image = mouth1
				case 1:
					if previous_sound_vol < 1:
						image = mouth3
					else:
						image = mouth4
				case 2:
					if previous_sound_vol < 2:
						image = mouth5
					else:
						image = mouth6
				case 3:
					if previous_sound_vol < 3:
						image = mouth7
					else:
						image = mouth8
				case 4:
					if previous_sound_vol < 4:
						image = mouth9
					else:
						image = mouth10
				case 5:
					if previous_sound_vol < 5:
						image = mouth11
					else:
						image = mouth12
				case 6:
					if previous_sound_vol < 6:
						image = mouth13
					else:
						image = mouth14
				case _:
					pass

			previous_sound_vol = sound_vol				

			screen.blit(image, (head_x, head_y))
			drawText(screen,text2speak, WHITE,text_box_rect,font2)
			pygame.display.update()

		# Stop and close the stream and PyAudio instance
		stream.stop_stream()
		stream.close()
		image = black_out
		screen.blit(image, (0,1400))
		pygame.display.update()
		randnum = random.randrange(0,20)
		if randnum >= 15:
			image = mouth2
		else:
			image = mouth1
		screen.blit(image, (head_x,head_y))
		pygame.display.update()
		p.terminate()
		wf.close()
		print("Finished playback.")
	except:
		traceback.print_exc()
		print("error playing wav file in speak_wav fxn")

def listen_for_speech():
	global presence 
	while(True):
		try:
			poll_presence()
			image = black_out
			screen.blit(image, (0,1400))
			pygame.display.update()
			randnum = random.randrange(0,4)
			if randnum == 1:
				image = mouth2
			else:
				image = mouth1
			screen.blit(image, (head_x,head_y))
			pygame.display.update()
			if presence:
				try:
					with sr.Microphone(device_index = 1) as source:
						# blink
						randnum = random.randrange(0,4)
						if randnum == 1:
							image = mouth2
						else:
							image = mouth1
						screen.blit(image, (head_x,head_y))
						pygame.display.update()						
						start_rec_time = int(time.time())
						text2display = "Background subtraction..."
						print(text2display)
						# display txt
						drawText(screen,text2display, WHITE,text_box_rect,font2)
						pygame.display.update()
						
						r.adjust_for_ambient_noise(source, duration = 1)
						
						# erase txt
						randnum = random.randrange(0,4)
						if randnum == 1:
							image = mouth2
						else:
							image = mouth1
						screen.blit(image, (head_x,head_y))
						text2display = "Listening..."	
						print(text2display)
						# display txt
						drawText(screen,text2display, WHITE,text_box_rect,font2)
						pygame.display.update()
						
						audio = r.listen(source)
						
						end_rec_time = int(time.time())
						total_rec_time = end_rec_time - start_rec_time
						# erase txt
						randnum = random.randrange(0,4)
						if randnum == 1:
							image = mouth2
						else:
							image = mouth1
						screen.blit(image, (head_x,head_y))
						#print("record time: ", total_rec_time, " seconds")				
				except KeyboardInterrupt:  # Ctrl+C pressed
					print("User involked 'ctr c' interupt in while loop, stopped program")
					break
				# erase previous display txt
				drawText(screen,text2display, BLACK,text_box_rect,font2)
				pygame.display.update()
				
				# try to recognize speech using whisper
				try:
					text2display = "thinking..."
					print(text2display)
					# display txt
					drawText(screen,text2display, WHITE,text_box_rect,font2)
					pygame.display.update()
					
					start_time_r = int(time.time())
					
					output_txt = r.recognize_google(audio)
					
					end_time_r = int(time.time())
					total_time_r = end_time_r - start_time_r
					# erase txt
					randnum = random.randrange(0,4)
					if randnum == 1:
						image = mouth2
					else:
						image = mouth1
					screen.blit(image, (head_x,head_y))
					
					if(len(output_txt) >=1):
						print("I think you said " + output_txt + ", len(output_txt): ",len(output_txt))
						# display txt
						text2display = "Input: " + output_txt
						drawText(screen,text2display, WHITE,text_box_rect,font2)
						pygame.display.update()
						pygame.time.delay(1000)
						# erase txt
						randnum = random.randrange(0,4)
						if randnum == 1:
							image = mouth2
						else:
							image = mouth1
						screen.blit(image, (head_x,head_y))
						
						lc_txt = output_txt.lower()
						if(lc_txt.count("die") >= 1):
							print(
							"OK, I will kill the program now")
							quit()		
						else:
							return output_txt
							
					else:
						print("len(output_txt) < 1")
						text2display = "Huh? I didn't catch that"
						# display txt
						drawText(screen,text2display, WHITE,text_box_rect,font2)
						pygame.display.update()
						pygame.time.delay(1000)
						# erase txt
						randnum = random.randrange(0,4)
						if randnum == 1:
							image = mouth2
						else:
							image = mouth1
						screen.blit(image, (head_x,head_y))						
				except sr.UnknownValueError:
					print("I could not understand audio")
				except sr.RequestError as e:
					print(f"Could not request results from Google; {e}")
			else:
				output_txt = "x o x bye."			
				return output_txt

		except KeyboardInterrupt:  # Ctrl+C pressed
			print("User involked 'ctr c' interupt in while loop, stopped program")
			break

def mistral_chat(txt):
	txt = txt
	print("Mistral input text: ",txt)
	chat_response = mistral_client.chat.complete(
		model=mistral_model,
		messages=[
			{
				"role": "system",
				"content": "You are an frustrated and overworked house servant. Your answers are sarcastic and witty, but answer the question asked.",
			},
			{
				"role": "system",
				"content": "Do not use periods in abbreviations like U.S.A.",
			},
			{
				"role": "user",
				"content": txt,
			},
			
		],
	)
	response_txt = chat_response.choices[0].message.content
	response_txt = response_txt.replace("*", "")
	return response_txt
		
print("Everything loaded, start main program")

#start a timer and set initial state
startTime = int(time.time())

# set the initial image as closed curtain
image = black_out

# set true to load vid first
cancel_ai_response = False

#draw screen
screen.blit(image, (0,0))
pygame.display.update()
	
date = datetime.now()
hour = date.strftime("%-I")
now_hour = int(hour)
hour_24 = date.strftime("%H")
now_hour_24 = int(hour_24)
minute = date.strftime("%-M")
minute_full = date.strftime("%M")
old_hour = int(hour)
old_minute = int(minute)

intOldHour = 25 #make diff from any first reading
intOldMin = 61 #make diff from any first reading
intOldSec = 61 #make diff from any first reading

morningMode=False
afternoonMode=False
nightMode=False
midnightMode=False
time_text = hour + ":" + minute_full
time_width, time_height = font.size(time_text)

print("playTime at start up")
playTime() # on startup

music_playing = False

presence = False
presence_start_time = int(time.time())
# start with 'closed curtain' (or black_out)
#curtain_closed = close_curtain()

try:
	while(True):
		try:
			# check for motion and/or presence
			poll_presence()
			# use this to cancel AI response (since speaks one sentnece at a time)
			button_cancel.when_pressed = on_button_cancel_pressed
			date = datetime.now()
			hour = date.strftime("%-I")
			now_hour = int(hour)
			hour_24 = date.strftime("%H")
			now_hour_24 = int(hour_24)
			minute = date.strftime("%-M")
			minute_full = date.strftime("%M")
			now_minute = int(minute)
			
			if(now_hour_24 >= 6 and now_hour_24 <= 11):
				morningMode = True
			else:
				morningMode = False

			if(now_hour_24 >= 12 and now_hour_24 <= 18):
				afternoonMode = True
			else:
				afternoonMode = False
				
			if(now_hour_24 >= 19 and now_hour_24 <= 21):
				nightMode = True
			else:
				nightMode = False
				
			if(now_hour_24 >= 22 or now_hour_24 < 6):
				midnightMode = True
			else:
				midnightMode = False
			
			if now_hour != old_hour:
				print("******************new hour********************")
				if not midnightMode:
					playTime()
					pygame.time.delay(1000)
				old_hour = now_hour

			nowTime = int(time.time())
			#print("presence: ",presence)
			if presence:
				presence_det_start_time = int(time.time())
				user_speech = listen_for_speech()
				print("Speak the user user_speech returned from speech recognition: ",user_speech)
				if (user_speech.find("x o x") == -1):
					mistral_response = mistral_chat(user_speech)
					mistral_arr=[]
					
					mistral_arr = mistral_response.split('.')
					for sentence in mistral_arr:
						button_cancel.when_pressed = on_button_cancel_pressed
						print("Mistral response sentence: ",sentence)
						if len(sentence.strip()) > 0:
							if cancel_ai_response:
								print("cancel button pressed, cancel_ai_response = True, cancel AI reading")
								pass
							else:
								file_2_speak = synth_2_mp3(sentence)
								if file_2_speak == None:
									print("None being returned, skip speak_wav")							
								else:
									speak_wav(file_2_speak,sentence)
					cancel_ai_response = False # reset for each recogonition event
				else:
					print("x o x, skip mistral,skip playTxt")
				
				if not music_playing:	
					pygame.mixer.music.load('fortune_teller/sounds/indian_background_music.mp3')
					pygame.mixer.music.set_volume(0.5)
					pygame.mixer.music.play(-1) # Loop until music.stop()
					music_playing = True
						# mouth_name = mouth_arr[mouth_num]
						# image = mouth_name
						# sleep_int = random.randint(500,1000)
						# pygame.time.delay(sleep_int)
						
						# show time
						# calculate width of time text to center
						# pygame.Rect(left, top, width, height)
				else:
					#print("music_playing: ",music_playing)
					if music_playing:
						music_playing = False
						pygame.mixer.music.stop()
				presence_det_start_time = int(time.time())
			else:
				presence_total_time = int(time.time()) - presence_det_start_time
				image = black_out
				screen.blit(image, (0,0))
				pygame.display.update()
				if presence_total_time < 30:
					# only draw new frames, and only update the screen if something is drawn
					vid_swirl.play()
					while vid_swirl.active:
						# only draw new frames, and only update the screen if something is drawn
						poll_presence()
						presence_total_time = int(time.time()) - presence_det_start_time
						if vid_swirl.draw(screen, (video_x, video_y), force_draw=False):
							pygame.display.update()
						vidActive = vid_swirl.active
						if not vidActive and not presence:
							vid_swirl.restart() # effectivly loops video
						pygame.time.wait(16) # around 60 fps
						button_select.when_pressed = on_button_select_pressed
						button_cancel.when_pressed = on_button_cancel_pressed
						if cancel_ai_response or presence or presence_total_time >= 30:
							print("vid_swirl.stop")
							vid_swirl.stop()
					print("vid_swirl.stop")
				else:
					image = black_out
					screen.blit(image, (0,0))
					pygame.display.update()
					image = black_out
					time_width, time_height = font2.size(time_text)
					time_box_rect = pygame.Rect((WIDTH/2)-(time_width/2), HEIGHT-time_height-50, time_width, time_height)
					drawText(screen,time_text, BLACK,time_box_rect,font2) #get rid of prev text
					time_text = hour + ":" + minute_full
					time_width, time_height = font2.size(time_text)
					time_box_rect = pygame.Rect((WIDTH/2)-(time_width/2), HEIGHT-time_height-50, time_width, time_height)
					screen.blit(image, (head_x, head_y))
					drawText(screen,time_text, WHITE,time_box_rect,font2)
					pygame.display.update()
			if old_minute != now_minute:
				old_minute = now_minute
			
			#print("end of while loop, return to top.  PIR_total_time: ",PIR_total_time,", curtain_time: ",curtain_time)
			pygame.time.wait(16) #processor rest time :)
		except:
			print("exception in main loop inside while loop, stopped program")
			traceback.print_exc()
			break # Exiting the loop allows automatic cleanup to occur

except KeyboardInterrupt:  # Ctrl+C pressed
	print("User involked 'ctr c' interupt in while loop, stopped program")
	presence_det.close()   # Clean up GPIO pins
	button_cancel.close()
	led.close()
	vid_globe_girl.close()
	traceback.print_exc()