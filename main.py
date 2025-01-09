import requests
import time
from typing import List, Dict
from dotenv import load_dotenv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

class SolanaTransactionFetcher:
    def __init__(self):
        self.base_url = "https://pro-api.solscan.io/v2.0"
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "token": os.environ.get("SOLSCAN_API_KEY")
        }
        self.kols = []
        with open("data/kols.txt", "r") as lines:
            for line in lines:
                self.kols.append(line.replace("\n",""))
        
    def process_addresses(self, data, market_cap):
        """
        Process a list of addresses with multithreading.
        """
        result = []
        with ThreadPoolExecutor(max_workers=10) as executor:  # Adjust max_workers as needed
            futures = {executor.submit(self.fetch_meta, add, market_cap, result): add for add in data}
            for future in as_completed(futures):
                add = futures[future]
                try:
                    future.result()  # If needed to catch exceptions
                except Exception as e:
                    print(f"Error processing address {add}: {e}")
        return result
    
    def fetch_holder(self, address, coin_suppy, threshold = 0.25, num_page = 5, page_size = 40):
        """
        Fetch metadata for a given token address.
        """
        items = []
        for page_i in range(1, num_page+1):
            url = self.base_url + f"/token/holders?address={address}&page={page_i}&page_size={page_size}"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200 and response.json().get("success", False):
                tmp = response.json().get("data", {})
                items += tmp['items']
        total = tmp['total']
        holders = []
        kols = []
        for item in items:
            item_amount = item['amount']
            item_address = item['address']
            if item_amount/coin_suppy < threshold:
                holders.append(item)
            if item_address in self.kols:
                kols.append(item)
        return {
            "total": total,
            "items": items,
            "kols": kols
        }
            
    
    def fetch_meta(self, add, market_cap, result):
        """
        Fetch metadata for a given token address.
        """
        url = self.base_url + f"/token/meta?address={add}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200 and response.json().get("success", False):
            coin_info = response.json().get("data", {})
            if coin_info and coin_info.get('market_cap', 0) > market_cap * 1e6:
                coin_suppy = int(coin_info['supply'])
                holders = self.fetch_holder(add, coin_suppy)
                coin_info['holders'] = holders
                result.append(coin_info)


    def get_coin(self, created_time = 24, market_cap = 1, page = 1, page_size = 100):
        data = []
        now = time.time()
        #get token within day
        for page_i in range(1,page+1):
            url = self.base_url + f"/token/list?sort_by=created_time&sort_order=desc&page={page_i}&page_size={page_size}"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200 and response.json().get("success", False):
                data += response.json().get("data", [])
        if data:
            data = [x["address"] for x in data if x.get("created_time", now-created_time*3600-100) > now - created_time*3600]
        result = self.process_addresses(data, market_cap)
        return result
        


    def get_transactions(self, wallet_address: str, limit: int = 10) -> List[Dict]:
        endpoint = f"{self.base_url}/account/transactions"
        params = {
            "account": wallet_address,
            "limit": limit
        }
        
        try:
            response = requests.get(
                endpoint,
                params=params,
                headers=self.headers
            )
            response.raise_for_status()
            
            if response.status_code == 200:
                return self._process_transactions(response.json())
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching transactions: {e}")
            return []
            
        # Handle rate limiting
        time.sleep(2)  # Respect rate limits
        
    def _process_transactions(self, data: List[Dict]) -> List[Dict]:
        processed_txns = []
        
        for tx in data:
            processed_tx = {
                'signature': tx.get('signature', ''),
                'block_time': tx.get('blockTime', ''),
                'slot': tx.get('slot', ''),
                'fee': tx.get('fee', 0),
                'status': tx.get('status', ''),
                'lamport': tx.get('lamport', 0)
            }
            processed_txns.append(processed_tx)
            
        return processed_txns

# Usage example
if __name__ == "__main__":
    fetcher = SolanaTransactionFetcher()
    
    print(fetcher.get_coin())
    
    # wallet = os.environ.get('API_KEY')
    # wallet = "AbcX4XBm7DJ3i9p29i6sU8WLmiW4FWY5tiwB9D6UBbcE"
    # transactions = fetcher.get_transactions(wallet, limit=5)
    
    # for tx in transactions:
    #     print(f"Signature: {tx['signature']}")
    #     print(f"Time: {tx['block_time']}")
    #     print(f"Status: {tx['status']}")
    #     print("---")