import httpx
from typing import Optional, Dict, Any, List
from app.core.config import settings

class TonService:
    def __init__(self):
        self.base_url = "https://toncenter.com/api/v2" if settings.TON_NETWORK == "mainnet" else "https://testnet.toncenter.com/api/v2"
        self.api_key = "" # Add TonCenter API key if available
        
    async def get_balance(self, address: str) -> str:
        async with httpx.AsyncClient() as client:
            params = {"address": address}
            if self.api_key:
                params["api_key"] = self.api_key
            
            resp = await client.get(f"{self.base_url}/getAddressInformation", params=params)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data["result"]["balance"] # In nanoTONs
            return "0"

    async def get_transactions(self, address: str, limit: int = 20) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            params = {"address": address, "limit": limit}
            if self.api_key:
                params["api_key"] = self.api_key
                
            resp = await client.get(f"{self.base_url}/getTransactions", params=params)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data["result"]
            return []

ton_service = TonService()

async def verify_ton_signature(wallet_address: str, public_key: str, signature: str, message: str) -> bool:
    """
    Verify TON wallet signature. 
    Expects signature in hex format and public_key in hex format.
    The message is typically the nonce string.
    """
    from tonsdk.crypto import verify_signature
    from tonsdk.utils import Address
    import binascii

    try:
        # 1. Basic validation of wallet address
        addr = Address(wallet_address)
        
        # 2. Verify signature using LibNaCL (via tonsdk)
        pub_key_bytes = binascii.unhexlify(public_key)
        sig_bytes = binascii.unhexlify(signature)
        
        # In a real TON Connect 2.0, the message is more complex (prefix + network + address + nonce).
        # For this simplified version, we sign the nonce directly.
        msg_bytes = message.encode('utf-8')
        
        return verify_signature(pub_key_bytes, sig_bytes, msg_bytes)
    except Exception as e:
        print(f"TON Signature Verification Failed: {e}")
        return False
