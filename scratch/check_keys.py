
import asyncio
import logging
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from vault import Vault
from dhatu_oracle import DhatuOracle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KeyChecker")

async def check_keys():
    logger.info("--- Sovereign Key Health Check ---")
    
    google_key = Vault.get("GOOGLE_API_KEY")
    anthropic_key = Vault.get("ANTHROPIC_API_KEY")
    
    if not google_key:
        logger.warning("?? GOOGLE_API_KEY: MISSING from Vault.")
    else:
        logger.info("?? GOOGLE_API_KEY: Present. Testing Gemini connection...")
        try:
            import google.generativeai as genai
            genai.configure(api_key=google_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            # Fast ping
            response = await asyncio.to_thread(model.generate_content, "ping")
            if response.text:
                logger.info("? GEMINI: SUCCESS. Connection established.")
        except Exception as e:
            logger.error(f"? GEMINI: FAILED. Error: {e}")

    if not anthropic_key:
        logger.warning("?? ANTHROPIC_API_KEY: MISSING from Vault.")
    else:
        logger.info("?? ANTHROPIC_API_KEY: Present. Testing Claude connection...")
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            # Fast ping
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}]
            )
            if response.content:
                logger.info("? CLAUDE: SUCCESS. Connection established.")
        except Exception as e:
            logger.error(f"? CLAUDE: FAILED. Error: {e}")

    logger.info("--- End of Check ---")

if __name__ == "__main__":
    asyncio.run(check_keys())
