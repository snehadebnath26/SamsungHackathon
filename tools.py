import os
from crewai import LLM, Agent, Task, Crew, Process
from crewai_tools import DirectorySearchTool
from crewai.tools import tool
from google.cloud import speech
import os
from pydub import AudioSegment
import wave
from groq import Groq
import base64
from dotenv import load_dotenv
import json
from google.oauth2 import service_account
# Load environment variables
load_dotenv()

# Tool: Equipment Identifier
@tool
def equipment_identifier(image_path:str)->str:
    """
    Takes the input image at {image_path} to identify the equipment present in the image.
    Args:
        image_path (str): Path to the image file to be analyzed.
    Returns:
        equipment_name (str) : identified equipment
    """
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's the equipment in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                        },
                    },
                ],
            }
        ],
        model="meta-llama/llama-4-scout-17b-16e-instruct",
    )
    equipment_name = chat_completion.choices[0].message.content
    return equipment_name

# Tool: Voice Input transcription
def _convert_to_mono(input_file:str)->str:
    """
    Converts a stereo audio file to a mono audio file.
    Args:
        input_file (str): Path to the input stereo audio file.
    Returns:
        output_file (str): Path to the output mono audio file.
    """
    audio = AudioSegment.from_file(input_file)
    audio = audio.set_channels(1)
    output_file = "uploaded_audio/output_mono.wav"
    audio.export(output_file, format="wav")
    return output_file

@tool
def transcribe_audio(input_file:str)->str:
    """
    Transcribes an audio file using Google's Speech-to-Text API.
    Args:
        input_file (str): Path to the audio file to be transcribed (should be mono).
    Returns:
        transcription (str) : transcribed text
    """
    mono_audio = _convert_to_mono(input_file)
    # Read raw audio content
    with open(mono_audio, "rb") as audio_file:
        audio_content = audio_file.read()
    
    audio = speech.RecognitionAudio(content=audio_content)

    # Detect sample rate from WAV file
    with wave.open(mono_audio, "rb") as wf:
        sample_rate_hertz = wf.getframerate()
    print(f"Detected sample rate: {sample_rate_hertz}")

    # Configure recognition
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate_hertz,
        language_code="en-US",
    )
    gcp_json_str = os.environ.get("GCP_KEY_JSON")

    # Convert string to dict
    gcp_credentials_dict = json.loads(gcp_json_str)

    # Create Credentials object
    credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)

    # Pass credentials to client
    client = speech.SpeechClient(credentials=credentials)
    # Call Google Speech-to-Text API
    response = client.recognize(config=config, audio=audio)

    transcription = ""
    # Print transcription results
    for result in response.results:
        transcription += result.alternatives[0].transcript
    
    return transcription

# Tool: search across PDFs in `.database/`
search_tool = DirectorySearchTool(directory='database/',
    config=dict(
        llm=dict(
            provider="google",  # Using Gemini as the LLM
            config=dict(
                model="gemini-1.5-flash",
            ),
        ),
        embedder=dict(
            provider="google",  # Use Gemini for embeddings
            config=dict(
                model="models/embedding-001",
                task_type="retrieval_document",
            ),
        ),
    )
)