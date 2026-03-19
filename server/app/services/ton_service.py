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
