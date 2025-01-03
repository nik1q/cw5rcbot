import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Logging configuration
LOGGING_LEVEL = logging.INFO  # Change this to logging.DEBUG if you want more detailed logs
LOG_FILE = "app.log"  # The log file name

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=LOGGING_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Bot API token (loaded from .env)
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise ValueError("Bot token not found. Please check your .env file.")

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot_database.db")

# Custom RateLimiter middleware
RATE_LIMIT = 1.0  # Set rate limit in seconds