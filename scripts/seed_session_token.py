import asyncio
import os
import sys
import pickle
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from bridge_app.database import get_db
from bridge_app.models import Credentials
from bridge_app.utils.crypto import encrypt

load_dotenv()

async def seed_session():
    print("Monarch Manual Session Seeder")
    print("-----------------------------")
    print("Since automated login is blocked (HTTP 525), use this script to manually save your session.")
    print("1. Log in to Monarch Money in your browser (Chrome/Edge/Firefox).")
    print("2. Open Developer Tools (F12) -> Network Tab.")
    print("3. Filter for 'graphql' or click any request to 'api.monarchmoney.com'.")
    print("4. Look at the Request Headers.")
    print("5. Copy the value of the 'Authorization' header. It should look like 'Token <long_string>'.")
    print("-----------------------------")

    email = os.getenv("MM_EMAIL")
    if not email:
        email = input("Monarch Email: ").strip()
    else:
        print(f"Using email from env: {email}")

    token_input = input("Paste your Authorization Token (e.g., 'Token ...' or just the token): ").strip()
    
    if not token_input:
        print("Token required.")
        return

    # Clean token
    if token_input.startswith("Token "):
        token = token_input.replace("Token ", "")
    else:
        token = token_input

    # Create session object expected by MonarchMoney library
    session_data = {
        "token": token,
        "headers": {
            "Accept": "application/json",
            "Client-Platform": "web",
            "Content-Type": "application/json",
            "User-Agent": "MonarchMoneyAPI (https://github.com/hammem/monarchmoney)",
            "Authorization": f"Token {token}"
        }
    }
    
    session_bytes = pickle.dumps(session_data)

    async for db in get_db():
        from sqlalchemy import select
        result = await db.execute(select(Credentials).where(Credentials.email == email))
        creds = result.scalar_one_or_none() # type: Credentials
        
        if creds:
             print(f"Updating session for {email}...")
             creds.monarch_session = session_bytes
        else:
             print(f"User {email} not found to attach session. Creating new record.")
             # Dummy payload for password flow (unused here)
             payload = encrypt('{"password": "", "mfa_secret": ""}')
             creds = Credentials(email=email, encrypted_payload=payload, monarch_session=session_bytes)
             db.add(creds)
        
        await db.commit()
        print("✅ Session manually saved! You should now be able to use the app.")
        break

if __name__ == "__main__":
    try:
        asyncio.run(seed_session())
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
