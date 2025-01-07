from sqlalchemy.exc import SQLAlchemyError
from config import engine, metadata, SessionLocal
from models import User, Squad
import logging

logger = logging.getLogger(__name__)

# Database initialization function
def on_startup():
     """Create the database schema."""
     metadata.create_all(engine)
     print("The database and tables have been created.")

# Functions to interact with the database
def add_user(session, user_data):
    try:
        new_user = User(**user_data)
        session.add(new_user)
        session.commit()
        logger.info(f"User {user_data['telegram_id']} added successfully.")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error adding user: {e}")
    finally:
        session.close()


def add_squad(session, squad_data):
    try:
        new_squad = Squad(**squad_data)
        session.add(new_squad)
        session.commit()
        logger.info(f"Squad {squad_data['chat_name']} added successfully.")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error adding squad: {e}")
    finally:
        session.close()
