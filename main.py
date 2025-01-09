import requests
import time
from typing import List, Dict
from dotenv import load_dotenv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dexsum.x_client import XClient
from typing import Literal
from report.llm import Reporter


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
        self.ignore_addresses = []
        self.stop_event = threading.Event()
        
    def load_ignore_address(self, path = "data/ignore_tokens.txt"):
        with open(path, "r") as lines:
            for line in lines:
                line = line.strip()
                if line not in self.ignore_addresses:
                    self.ignore_addresses.append(line)
    
    def process_addresses(self, data, volume):
        """
        Process a list of addresses with multithreading.
        """
        result = []
        futures = []
        with ThreadPoolExecutor(max_workers=10) as executor:  # Adjust max_workers as needed
            for add in data:
                future = executor.submit(self.fetch_meta, add, volume, result, futures)
                futures.append(future)
            for future in as_completed(futures):
                if self.stop_event.is_set():
                    break
                try:
                    future.result()  # Handle individual task errors if needed
                except Exception as e:
                    print(f"Error processing address: {e}")
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
            
    def fetch_meta(self, add, volume, result, futures):
        """
        Fetch metadata for a given token address.
        """
        add = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
        url = self.base_url + f"/token/meta?address={add}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200 and response.json().get("success", False):
            coin_info = response.json().get("data", {})
            if coin_info and coin_info.get('volume_24h', 0) > volume * 1e6:
                coin_suppy = int(coin_info['supply'])
                holders = self.fetch_holder(add, coin_suppy)
                coin_info['holders'] = holders
                result.append(coin_info)
                self.stop_event.set()
                for future in futures:
                    future.cancel()

    def get_coin(self, created_time = 24, volume = 1, page = 1, page_size = 100):
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
        print("number data per day: ", len(data))
        result = self.process_addresses(data, volume)
        return result
        
    def calculate_score(self, token_data : dict):
        score = 40
        # cộng điểm theo holder
        if len(token_data['holders']['kols']) > 0:
            score += 10
        return score
    
    def get_social(self, token_address: str, type_social: Literal["twitter","telegram"] = None):
        url = f'https://api.dexscreener.com/latest/dex/pairs/solana/{token_address}'
        response = requests.get(url)
        if response.status_code == 200 and response:
            response = response.json()
            socials = response.get("pair", {}).get("info",{}).get("socials", [])
        if type_social:
            for social in socials:
                if social['type'] == type_social:
                    return social['url']
        return socials
    
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
    
    API_KEY = os.environ['API_KEY']
    API_SECRET_KEY = os.environ['API_SECRET_KEY']
    ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
    ACCESS_TOKEN_SECRET = os.environ['ACCESS_TOKEN_SECRET']
    BEARER_TOKEN = os.environ["BEARER_TOKEN"]
    CLIENT_ID = os.environ["CLIENT_ID"]
    CLIENT_SECRET = os.environ["CLIENT_SECRET"]

    OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
    TELE_TOKEN = os.environ['TELE_TOKEN']
    TELE_GROUP_ID = os.environ['TELE_GROUP_ID']

    #define object
    fetcher = SolanaTransactionFetcher()
    x_client = XClient(
        bearer_token= BEARER_TOKEN,
        consumer_key= API_KEY,
        consumer_secret= API_SECRET_KEY,
        access_token= ACCESS_TOKEN,
        access_token_secret= ACCESS_TOKEN_SECRET
    )
    reporter = Reporter()
    
    # coin information
    result = fetcher.get_coin(page = 1, page_size = 100)
    promise_token = result[0]
    
    #  analyze narrative
    tweet = fetcher.get_social("95ecyahcxcecupe1mrjdsbt82acqke2ocna9ffq9bicf", type_social = "twitter")
    if tweet:
        tweet = tweet.replace("https://x.com/","")

    # tweets = x_client.get_latest_tweet(tweet, 5)
    # texts = ""
    # if tweets:
    #     texts = "\n".join(tweets['texts'])
    texts = "\n".join([
        """Extra Large Language Model $XLLM Is now Live !

ca - 9aLx5SCcoacuK4VVmucy3yu7smR37TWXFyTHnxUQpump

chart - https://dexscreener.com/solana/95ecyahcxcecupe1mrjdsbt82acqke2ocna9ffq9bicf

tg - https://t.me/xllmonsol

First 777 wallets will be eligible for 1,000,000 $XLLM Airdrop !""",

"""To Celebrate 3,000 Holders,

giving away 3,000$ $XLLM to try help some people out
picking 3 people, 1000$ each
just reply to enter, no need to follow just wanna help ppl

ending in 8hour-ish"""
    ])
    trending_narrative = """Rebellion against the status quo: Hunger games, Oblivion, 12 Years a slave, in a world of complexity, ruled by dynamics which people feel are out of their direct control, rebellion is a theme that resonates deeply and generates powerful resonance."""
    analysis = reporter.analyse("trending is true story of AI", texts)

    #calculate score
    score = fetcher.calculate_score(promise_token)
    
    
    report = reporter.make_report("XLLM", analyse =analysis, aisem_score= score )
    print(report)