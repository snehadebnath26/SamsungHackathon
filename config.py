import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Application settings
APP_TITLE = "Aura - AI Supervisor for Enterprise Operations"
APP_ICON = "🌐"

# Directory configuration
BASE_DIR = Path(__file__).parent
UPLOADED_IMAGE_DIR = BASE_DIR / "uploaded_image"
UPLOADED_AUDIO_DIR = BASE_DIR / "uploaded_audio"

# File settings
AUDIO_FILENAME = "sample_audio.wav"
ALLOWED_IMAGE_TYPES = ["jpg", "jpeg", "png"]
ALLOWED_AUDIO_TYPES = ["wav", "mp3", "m4a"]

# UI Configuration
CONTAINER_HEIGHT = 600
IMAGE_DISPLAY_WIDTH = 250
MAX_RESPONSE_DISPLAY_LENGTH = 2000

# Agent configuration
AGENT_TIMEOUT = 300  # 5 minutes timeout
MAX_RETRIES = 3

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Environment variables
REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "GOOGLE_API_KEY"  # Required by DirectorySearchTool
]

# Validate environment
def validate_environment():
    """Check if all required environment variables are set"""
    missing_vars = []
    
    # Check GEMINI and GROQ keys
    for var in ["GEMINI_API_KEY", "GROQ_API_KEY"]:
        if not os.getenv(var):
            missing_vars.append(var)
    
    # Set GOOGLE_API_KEY to GEMINI_API_KEY if not set (they're the same service)
    if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")
    elif not os.getenv("GOOGLE_API_KEY"):
        missing_vars.append("GOOGLE_API_KEY (or GEMINI_API_KEY)")
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
    
    return True

# Create necessary directories
def ensure_directories():
    """Ensure all required directories exist"""
    directories = [UPLOADED_IMAGE_DIR, UPLOADED_AUDIO_DIR]
    
    for directory in directories:
        directory.mkdir(exist_ok=True, parents=True)
    
    return True
