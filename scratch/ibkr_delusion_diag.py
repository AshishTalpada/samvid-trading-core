import asyncio
import logging
import sys
import os

# Add src to the path so we can import the Vault
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from ib_insync import IB
from vault import Vault

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IBKR_DIAG")

async def diag():
    ib = IB()
    try:
        from config import IBKR_HOST, IBKR_PAPER_PORT, IBKR_CLIENT_ID
        logger.info(f"Connecting to {IBKR_HOST}:{IBKR_PAPER_PORT} (Client {IBKR_CLIENT_ID})...")
        await ib.connectAsync(IBKR_HOST, IBKR_PAPER_PORT, clientId=IBKR_CLIENT_ID)
        
        print("\n=== IBKR ACCOUNT SUMMARY ===")
        accounts = ib.wrapper.accounts
        print(f"Available Accounts: {accounts}")
        
        for acc in accounts:
            summary = ib.accountSummary(account=acc)
            net_liq = next((item.value for item in summary if item.tag == "NetLiquidation"), "N/A")
            currency = next((item.value for item in summary if item.tag == "Currency"), "USD")
            print(f"Account: {acc} | NetLiq: {net_liq} {currency}")
            
        current_vault_id = Vault.get("IBKR_ACCOUNT_ID")
        print(f"\nVault IBKR_ACCOUNT_ID: '{current_vault_id}'")
        
        if current_vault_id and current_vault_id not in accounts:
            print(f"🚨 WARNING: Vault ID '{current_vault_id}' matches NONE of the available accounts!")
            if accounts:
                print(f"👉 SUGGESTION: Update your Vault to use: '{accounts[0]}'")
            
    except Exception as e:
        logger.error(f"Diag failed: {e}")
    finally:
        ib.disconnect()

if __name__ == "__main__":
    asyncio.run(diag())
