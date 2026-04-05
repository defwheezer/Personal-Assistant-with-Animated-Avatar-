Project Overview
This project builds upon the previous "Talking Avatar" project by integrating voice recognition and LLM-driven responses. The talking_avatar_assistant.py script serves as the core logic for a voice-activated personal assistant featuring a lip-synced animated avatar. It integrates speech recognition (via the SpeechRecognition library), artificial intelligence (utilizing the free version of Mistral), and media playback (Pygame for animations and PyAudio for sound) to create an interactive, sassy "butler" experience.

Core Functionalities
Voice Command Processing: The script listens for audio prompts via a USB microphone and uses the SpeechRecognition library to convert spoken words into text commands.

AI-Generated Responses: It processes user queries via the Mistral LLM API to synthesize context-aware text responses (for the demo the prompt includes "You are an frustrated and overworked house servant. Your answers are sarcastic and witty, but answer the question asked.".

Audio Synthesis (TTS): The AI's text response is converted into speech using either Whisper (local) or ElevenLabs for the very expressive voice, providing the voice synthesis for the assistant.

Lip-Synced Animation: A key feature of this script is its ability to synchronize the animated avatar’s mouth movements with the generated audio. It utilizes assets from the following repository folders:

Images: Uses frames from butler_images.zip to display character mouth shapes (this is where pygame comes in handy to keep and constant frame rate timing for the whole program).

Video/Audio: Integrates components from butler_videos.zip and butler_sounds.zip to create a cohesive audiovisual output.

Real-time Interaction: The system is designed to loop, waiting for a human presence detector to trigger the "listen" state. It then responds to audio prompts while displaying the corresponding animations.

Core Scripts & Configuration
talking_avatar_assistant.py: The main Python script that manages the lip-synced avatar, audio prompts, and AI responses.

requirements.txt: Contains the necessary Python dependencies to run the project.

LICENSE: The project is shared under a CC0-1.0 license.

Assets & Media
butler_videos.zip: Compressed video files used for loops during the assistant's "resting" state.

butler_sounds.zip: Compressed audio assets for background ambient sound.

butler_images.zip: Image assets featuring various mouth shapes for the avatar's lip-synching.

demo.mp4: A video demonstration of the assistant in action.
