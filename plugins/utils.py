from pyrogram import Client

from config import Config

async def start_clone_bot(user_client: Client) -> Client:
    """Start and return clone bot client"""
    await user_client.start()
    return user_client

def user_client(session: str) -> Client:
        """Create user client with session"""
        return Client("USERclient", Config.API_ID, Config.API_HASH, session_string=session)
