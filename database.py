# Bot database
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

#connect to DB
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=True)
SessionLocal = sessionmaker(autocommit = False, autoflush=False, bind=engine)
Base = declarative_base()

# Table of users from the game bot
class User(Base):
    __tablename__ = "users"
    # user player info
    id = Column(Integer, primary_key=True, index = True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, index=True)
    first_name = Column(String)
    last_name = Column(String)
    language = Column(String)
    timezone_offset = Column(Integer, default=0) # Player Time Zone UTC. For example +3 or -5
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    # equipment and statistics from the game
    hero_info = Column(JSON) # forwarded message with /hero
    last_hero_update = Column(DateTime, nullable=True)
    bag = Column(JSON)       # forwarded message with /bag
    last_bag_update = Column(DateTime, nullable=True)
    numbers = Column(JSON)   # forwarded message with /numbers
    last_numbers_update = Column(DateTime, nullable=True)

    # role and status,
    ## player - the user who forwarded their profile/hero
    ## mentor - can change the player's status trusted/untrusted, leave comments on the player's profile
    ## owner - everything a mentor can do, plus assign/remove mentors

    role = Column(String, default="player")
    trust_status = Column(String)

    # Recruit profile (one-to-one relationship)
    recruit_profile = relationship("RecruitProfile", uselist=False, back_populates="user")


# Translation
class Translation(Base):
    __tablename__ = "translations"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, index=True)
    language = Column(String, index=True)
    text = Column(String)


# Test Questions table for storing questions in multiple languages
class TestQuestion(Base):
    __tablename__ = "test_questions"
    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(String, nullable=False)
    language = Column(String, index=True, nullable=False)  # e.g., "en", "ru"
    test_name = Column(String, index=True)  # To group questions for a specific test or section
    position = Column(Integer, nullable=False)  # The order of the question in the test
    max_length = Column(Integer, nullable=True)  # Optional: Limit on characters for open-text responses


# Recruit Profile table to store recruit's test progress and answers
class RecruitProfile(Base):
    __tablename__ = "recruit_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    test_results = Column(JSON)  # JSON to store answers, keyed by question ID
    overall_score = Column(Integer, nullable=True)  # Optional overall score
    attempt_count = Column(Integer, default=1)  # Track the number of attempts
    current_question = Column(Integer, default=1)  # Track the current question position
    date_of_profile_creation = Column(DateTime, default=datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="recruit_profile")
    mentor_comments = relationship("MentorComment", back_populates="recruit_profile")


# Mentor Comments table
class MentorComment(Base):
    __tablename__ = "mentor_comments"
    id = Column(Integer, primary_key=True, index=True)
    recruit_profile_id = Column(Integer, ForeignKey("recruit_profiles.id"))
    mentor_id = Column(Integer, ForeignKey("users.id"))  # Assuming mentors are also stored in `User`
    comment = Column(String)
    rating = Column(Integer)  # Optional, could store a score/rating
    date_created = Column(DateTime, default=datetime.now(timezone.utc))

    # Relationships
    recruit_profile = relationship("RecruitProfile", back_populates="mentor_comments")
    mentor = relationship("User", foreign_keys=[mentor_id])

# squads table
class Squad(Base):
    __tablename__ = "squads"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, unique=True, index=True, nullable=False)  # Telegram chat ID
    chat_name = Column(String, nullable=True)  # Telegram chat name
    squad_name = Column(String, nullable=True)  # Squad name
    commander_ids = Column(JSON, nullable=True)  # List of Telegram IDs of squad commanders
    status = Column(String, default="untrusted")  # Squad status (trusted/untrusted)
    activity = Column(String, default="active")  # Squad activity status (active/inactive)
    timezone_offset = Column(Integer, default=0)  # UTC offset for notifications
    language = Column(String, default="ru")  # Squad language
    members = relationship("ChatMember", back_populates="squad")

# Updated table for chat members, linked to a squad
class ChatMember(Base):
    __tablename__ = "chat_members"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, index=True)
    username = Column(String, index=True)
    first_name = Column(String)
    last_name = Column(String)
    last_updated = Column(DateTime, default=datetime.now(timezone.utc))
    squad_id = Column(Integer, ForeignKey("squads.id"))  # Link to the squads table
    squad = relationship("Squad", back_populates="members")  # Reference to the squad


# Database initialization function
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database and tables created successfully.")
    except SQLAlchemyError as e:
        logger.critical(f"Database initialization failed: {e}")
    except Exception as e:
        logger.critical(f"Unexpected error during database initialization: {e}")


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


if __name__ == "__main__":
    init_db()
    print("The database and tables have been created.")