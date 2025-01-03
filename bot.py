import logging
from abc import ABC
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.exc import SQLAlchemyError
from config import API_TOKEN, LOG_FILE, RATE_LIMIT
from aiogram import Bot, types, BaseMiddleware, Router, Dispatcher
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime, timezone, timedelta
from database import SessionLocal, User, Translation
from dotenv import load_dotenv

load_dotenv() # Load environment variables

logger = logging.getLogger(__name__)
# Logging configuration
logging.basicConfig(
    filename=LOG_FILE,  # Use the LOG_FILE value from config.py
    level=logging.INFO,  # Set the logging level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Log format
    )

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage=MemoryStorage()
router = Router()

# start message
START_MESSAGE = (
    "To access the bot's functionality, please send your current /hero from Chat Wars.\n\n"
    "Para acceder a la funcionalidad del bot, envíe su /hero actual desde Chat Wars.\n\n"
    "Для получения доступа к функционалу бота, отправьте актуальный /hero из Chat Wars."
)

SUCCESS_MESSAGE = (
    "Data successfully updated.\n\n"
    "Datos actualizados con éxito.\n\n"
    "Данные обновлены успешно."
)

UNAUTHORIZED_MESSAGE = (
    "Access is allowed only for Red Castle players.\n\n"
    "El acceso está permitido solo para los jugadores del Castillo Rojo.\n\n"
    "Доступ разрешён только для игроков красного замка."
)

# Additional message for language selection
LANGUAGE_PROMPT = (
    "Please select a language by using /set_en.\n\n"
    "Por favor seleccione un idioma usando /set_es.\n\n"
    "Пожалуйста, выберите язык, используя /set_ru."
)


# Handle /start command
@router.message(Command("start"))
async def start_command(message: types.Message):
    """Handle /start command and send the initial message."""
    if message.chat.type != "private":
        return  # Ignore command if it's not in a private chat
    await message.answer(START_MESSAGE)


# Custom RateLimiter middleware
class RateLimiterMiddleware(BaseMiddleware, ABC):
    def __init__(self):
        super().__init__()
        self.users_last_message = {}

    async def __call__(self, handler, event: types.Message, data: dict):
        user_id = event.from_user.id
        now = datetime.now()

        last_time = self.users_last_message.get(user_id)

        if last_time and (now - last_time).total_seconds() < RATE_LIMIT:
            await event.answer("You're sending messages too quickly. Please wait a moment.")
            return

        self.users_last_message[user_id] = now
        return await handler(event, data)

# Add RateLimiterMiddleware instance to Dispatcher
router.message.middleware(RateLimiterMiddleware())


# Process forwarded /hero message
@router.message(lambda msg: msg.forward_from and msg.forward_from.username == "ChatWarsBot")
async def process_forwarded_message(message: types.Message):
    """Handles forwarded messages from ChatWarsBot and processes them based on content."""
    if message.chat.type != "private":
        return  # Ignore if not in a private chat

    # Ensure the forwarded message is recent
    time_diff = datetime.now(timezone.utc) - message.forward_date
    if time_diff > timedelta(seconds=40):
        await message.answer(START_MESSAGE)
        return

    session = SessionLocal()
    try:
        # Check if user exists in the database
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()

        if not user:
            # Register the new user
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                language="en",  # Default language for new users
                created_at=datetime.now(timezone.utc),
            )
            session.add(user)
            session.commit()
            await message.answer(START_MESSAGE)
            await message.answer(LANGUAGE_PROMPT)  # Send language prompt only for new users
            return  # Stop further processing until the user forwards their /hero

        # Determine the type of forwarded message
        if "🗡️Attack Force:" in message.text:
            # Process /hero message
            await process_hero_message(message, user, session)
        elif "🧳Equipment" in message.text:
            # Process /bag message
            await process_bag_message(message, user, session)
        elif "Additional info" in message.text:
            # Process /numbers message
            await process_numbers_message(message, user, session)
        else:
            await message.answer("Unrecognized message format. Please send /hero, /bag, or /numbers.")

    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        await message.answer("An error occurred while processing your request.")
    finally:
        session.close()

async def process_hero_message(message, user, session):
    """Processes and updates hero data for the user."""
    is_red_castle = message.text.startswith("🇮🇲")
    user.trust_status = "trusted" if is_red_castle else "untrusted" # player status
    user.hero_info = message.text
    user.last_hero_update = datetime.now(timezone.utc)
    session.commit()
    if is_red_castle:
        await message.answer(SUCCESS_MESSAGE)
    else:
        await message.answer(UNAUTHORIZED_MESSAGE)
    logger.info(f"Setting trust_status for user {user.telegram_id} to {'trusted' if is_red_castle else 'untrusted'}")

async def process_bag_message(message, user, session):
    """Processes and updates bag data for the user."""
    user.bag = message.text
    user.last_bag_update = datetime.now(timezone.utc)
    session.commit()
    success_message = await get_translated_message("operation_successful", user.language, session)
    await message.answer(success_message)

async def process_numbers_message(message, user, session):
    """Processes and updates numbers data for the user."""
    user.numbers = message.text
    user.last_numbers_update = datetime.now(timezone.utc)
    session.commit()
    success_message = await get_translated_message("operation_successful", user.language, session)
    await message.answer(success_message)

async def get_translated_message(key, language, session):
    """Fetches a translated message based on key and language."""
    translation = session.query(Translation).filter(
        Translation.key == key,
        Translation.language == language
    ).first()
    return translation.text if translation else "Operation completed successfully."


# Menu access check function
async def check_user_access(user, session):
    """Check if the user has trusted status and data is up-to-date."""
    # Calculate the time difference from the last hero update
    time_since_last_update = datetime.now(timezone.utc) - user.last_hero_update

    if user.trust_status != "trusted":
        # Get the untrusted access error message from the Translation table
        error_message = (
            session.query(Translation.text)
            .filter(Translation.key == 'access_denied_untrusted', Translation.language == user.language)
            .scalar()
        )
        return False, error_message or "Access to the bot is denied due to loss of trust."

    if time_since_last_update > timedelta(hours=48):
        # Get the outdated data error message from the Translation table
        error_message = (
            session.query(Translation.text)
            .filter(Translation.key == 'data_outdated', Translation.language == user.language)
            .scalar()
        )
        return False, error_message or "Your data is outdated. Please forward a new /hero from the game."

    # User has access
    return True, None

# Bot Menu
@router.message(Command("menu"))
async def show_menu(message: types.Message):
    """Show a simple menu with buttons for the player role."""
    logger.info(f"Menu command received from {message.from_user.id}")
    # Ensure the command is in a private chat
    if message.chat.type != "private":
        return  # Ignore command if it's not in a private chat

    session = SessionLocal()
    try:
        # Retrieve the user from the database
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()

        # Check if the user exists
        if not user:
            await message.answer("Please send your /hero to access the menu.")
            return

        # Check user's role and set up the menu
        if user.role == "player":
            # Define the menu buttons (constant for reuse)
            menu_buttons = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Profile", callback_data="profile"),
                    InlineKeyboardButton(text="Settings", callback_data="settings"),
                    InlineKeyboardButton(text="Info", callback_data="info")
                ]
            ])



            # Send the menu
            await message.answer("Player menu:", reply_markup=menu_buttons)
        else:
            await message.answer("Role-specific menus are not implemented yet.")
    finally:
        session.close()

# Registriere den Callback-Handler mit dem Router
@router.callback_query(lambda call: call.data == "profile")
async def handle_profile(call: CallbackQuery):
    """Handle the 'Profile' button."""
    await call.message.edit_text(
        text="This is your profile (placeholder).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Back to Menu", callback_data="menu")
            ]
        ])
    )
    await call.answer()  # Close the callback notification

@router.callback_query(lambda call: call.data == "settings")
async def handle_settings(call: CallbackQuery):
    """Handle the 'Settings' button."""
    await call.message.edit_text(
        text="Here you can adjust your settings (placeholder).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Back to Menu", callback_data="menu")
            ]
        ])
    )
    await call.answer()  # Close the callback notification

@router.callback_query(lambda call: call.data == "info")
async def handle_settings(call: CallbackQuery):
    """Handle the 'info' button."""
    await call.message.edit_text(
        text="Here you can adjust your settings (placeholder).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Back to Menu", callback_data="menu")
            ]
        ])
    )
    await call.answer()  # Close the callback notification


# Back to Menu Handler
@router.callback_query(lambda call: call.data == "menu")
async def handle_back_to_menu(call: CallbackQuery):
    """Handle the 'Back to Menu' button."""
    session = SessionLocal()
    try:
        # Retrieve the user from the database
        user = session.query(User).filter(User.telegram_id == call.from_user.id).first()

        # Check if the user exists
        if not user:
            await call.message.edit_text("Please send your /hero to access the menu.")
            return

        # Check user's role and set up the menu
        if user.role == "player":
            # Define the menu buttons (constant for reuse)
            menu_buttons = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Profile", callback_data="profile"),
                    InlineKeyboardButton(text="Settings", callback_data="settings"),
                    InlineKeyboardButton(text="Info", callback_data="info")
                ]
            ])

            # Update the menu
            await call.message.edit_text("Player menu:", reply_markup=menu_buttons)
        else:
            await call.message.edit_text("Role-specific menus are not implemented yet.")
    finally:
        session.close()
    await call.answer()  # Close the callback notification

# set language
async def set_language_command(message: types.Message, language_code: str):
    """Sets the user's language preference and sends a success message."""
    if message.chat.type != "private":
        return  # Ignore command if it's not in a private chat

    session = SessionLocal()
    try:
        # Check if the user exists in the database
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer(START_MESSAGE)
            return

        # Update the existing user's language preference
        user.language = language_code
        session.commit()

        # Retrieve the success message text from the Translation table
        success_message = (
            session.query(Translation.text)
            .filter(Translation.key == 'operation_successful', Translation.language == language_code)
            .scalar()
        )

        # Send the success message to the user
        await message.answer(success_message if success_message else "Operation completed successfully")

    finally:
        # Close the database session
        session.close()

# Handlers for language selection commands
@router.message(Command("set_ru"))
async def set_ru_command(message: types.Message):
    """Handles the /set_ru command to set the language to Russian."""
    await set_language_command(message, "ru")

@router.message(Command("set_en"))
async def set_en_command(message: types.Message):
    """Handles the /set_en command to set the language to English."""
    await set_language_command(message, "en")

@router.message(Command("set_es"))
async def set_es_command(message: types.Message):
    """Handles the /set_es command to set the language to Spanish."""
    await set_language_command(message, "es")

# Handle /set_language command
@router.message(Command("set_language"))
async def set_language_prompt(message: types.Message):
    """Sends the language selection prompt if the user has sent their /hero."""
    if message.chat.type != "private":
        return  # Ignore command if it's not in a private chat

    session = SessionLocal()
    try:
        # Check if the user exists in the database
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer(START_MESSAGE)
            return

        # Send the language selection prompt
        await message.answer(LANGUAGE_PROMPT)

    finally:
        # Close the database session
        session.close()


# Main function to run the bot
async def main():
    """Start bot polling."""
    logger.info("Bot started successfully.")
    dp = Dispatcher(storage=storage)
    dp.include_router(router) # Register routers
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())