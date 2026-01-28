import asyncio
import json
import os
import sys
from dotenv import load_dotenv, find_dotenv

# Debug info
print(f"Current Directory: {os.getcwd()}")
env_file = find_dotenv(usecwd=True)
print(f"Found .env file: {env_file}")
loaded = load_dotenv(env_file)
print(f"Loaded .env: {loaded}")
print(f"FERNET_KEY Present: {'Yes' if os.getenv('FERNET_KEY') else 'No'}")

# Add project root to path
sys.path.append(os.getcwd())

from bridge_app.database import get_db, engine
from bridge_app.models import Credentials
from bridge_app.utils.crypto import encrypt

async def list_users(session):
    from sqlalchemy import select
    result = await session.execute(select(Credentials))
    return result.scalars().all()

async def seed():
    print("Monarch Credential Manager")
    print("--------------------------")
    
    # Try getting from env first
    email = os.getenv("MM_EMAIL")
    if not email:
        email = input("Monarch Email: ").strip()
    else:
        print(f"Using email from env: {email}")

    if not email:
        print("Email is required.")
        return

    password = os.getenv("MM_PWD")
    if not password:
        password = input("Monarch Password: ").strip()
    else:
        print("Using password from env.")

    if not password:
        print("Password is required.")
        return

    mfa = input("MFA Secret (Base32) [Optional]: ").strip()
    
    payload = json.dumps({
        "password": password,
        "mfa_secret": mfa if mfa else None
    })
    
    async for session in get_db():
        # Check existing
        from sqlalchemy import select
        result = await session.execute(select(Credentials).where(Credentials.email == email))
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Updating credentials for {email}...")
            existing.encrypted_payload = encrypt(payload)
            # Clear session on password change
            existing.monarch_session = None
        else:
            print(f"Creating new user {email}...")
            new_cred = Credentials(email=email, encrypted_payload=encrypt(payload))
            session.add(new_cred)
            
        await session.commit()
        print("Success! Credentials saved.")
        break

if __name__ == "__main__":
    if not os.getenv("FERNET_KEY"):
        print("Error: FERNET_KEY not found. Run standard setup first.")
        exit(1)
        
    try:
        asyncio.run(seed())
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        print(f"\nError: {e}")
