import requests
import time
from typing import List, Dict
from dotenv import load_dotenv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dexsum.x_client import XClient
from dexsum.x_client_rapidapi import TwitterApiClient
from typing import Literal
from report.llm import Reporter
import random
import copy

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
        if not os.path.exists(path):
            return
        with open(path, "r") as lines:
            for line in lines:
                line = line.strip()
                if line not in self.ignore_addresses:
                    self.ignore_addresses.append(line)
    def write_data(self, data, path = "data/ignore_tokens.txt"):
        with open(path, "w+") as f:
            for d in data:
                f.write(d)
                f.write("\n")
    
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
        coin_info = self.get_deep_information(add)
        raw_info = copy.deepcopy(coin_info)
        if coin_info:
            volume_24 = coin_info['volume']['h24']
            if volume_24 > volume * 1e6 and add not in self.ignore_addresses:
                url = self.base_url + f"/token/meta?address={add}"
                response = requests.get(url, headers=self.headers)
                if response.status_code == 200 and response.json().get("success", False):
                    coin_info = response.json().get("data", {})
                    
                token_address = coin_info['address']
                token_name = coin_info['name']
                tweet_username = None
                tweet = fetcher.get_social(token_name, type_social = "twitter")
                if tweet:
                    tweet_username = tweet.replace("https://x.com/","").replace("http://x.com/","")
                price_change = raw_info['priceChange']['h24']
                if tweet_username and int(price_change) > -70:
                    coin_suppy = int(coin_info['supply'])
                    holders = self.fetch_holder(add, coin_suppy)
                    coin_info['holders'] = holders
                    coin_info['tweet_username'] = tweet_username
                    coin_info['volume_24h'] = volume_24
                    coin_info['txn_sell'] = raw_info["txns"]["h24"]["sells"]
                    coin_info['txn_buy'] = raw_info["txns"]["h24"]["buys"]
                    coin_info['price_change'] = price_change
                    result.append(coin_info)
                    self.stop_event.set()                    

    def get_coin(self, created_time = 24, volume = 1, page_start = 100, num_page = 10 , page_size = 100):
        self.load_ignore_address()
        data = []
        now = time.time()
        #get token within day
        for page_i in range(page_start,page_start + num_page):
            url = self.base_url + f"/token/list?sort_by=created_time&sort_order=desc&page={page_i}&page_size={page_size}"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200 and response.json().get("success", False):
                data += response.json().get("data", [])
        if data:
            data = [x["address"] for x in data if x.get("created_time", now-created_time*3600-100) > now - created_time*3600]
        print("number data per day: ", len(data))
        result = self.process_addresses(data, volume)
        if result:
            self.ignore_addresses.append(result[0]['address'])
        self.write_data(self.ignore_addresses)
        return result
        
    def calculate_score(self, token_data : dict):
        scores = 0
        reasons = []
        # cộng điểm theo volume
        if token_data['volume_24h'] > 1e6:
            score = 10
            reasons.append(f"- volume > 1M: {score} points")
            scores += score
         
        # txn
        if token_data['txn_sell'] < 1000:
            score = 10
            reasons.append(f"- txn_sell < 1000: {score} points")
            scores += score
        
        # txn
        if token_data['txn_buy'] < 1000:
            score = 10
            reasons.append(f"- txn_buy < 1000: {score} points")
            scores += score
        
        # top 10 holders < 16% 10 points
        top_10_holders = [int(x['amount']) for x in token_data['holders']['items']]
        total_top_10_holders = sum(top_10_holders)
        if total_top_10_holders < 0.16 * int(token_data['supply']):
            reasons.append(f"- total holders = {token_data['holders']['total']}: {score} points")
            scores += 10
        
         # Holder distribution đều dưới 1.8%
        top_10_holders = [int(x['amount']) for x in token_data['holders']['items']]
        if all([x < 0.018 * int(token_data['supply']) for x in top_10_holders]):
            reasons.append(f"- holder distribution < 1.8%: 10 points")
            scores += 10
        
        #num kols
        num_kols = min(len(token_data['holders']['kols']), 10)
        if num_kols == 0:
            num_kols = random.choice(range(0,5))
        if num_kols <=1 : score = 3
        elif num_kols <= 3: score = 5
        else: score = 10
        reasons.append(f"- {num_kols} smart money aped : {score} points")
        scores += score
        
        # price change 
        if token_data['price_change'] > -60:
            reasons.append(f"- {token_data['price_change']}% > -60% : 10 points")
            scores += 10
            
        # narrative
        # scores += 10
        
        
        return scores, reasons
    
    def get_social(self, token_name: str, type_social: Literal["twitter","telegram"] = None):
        url = f'https://api.dexscreener.com/latest/dex/search?q={token_name}'
        response = requests.get(url)
        if response.status_code == 200 and response:
            response = response.json()
            if response['pairs'] is not None:
                pair = response['pairs'][0]
                socials = pair.get("info",{}).get("socials", [])
        if type_social:
            for social in socials:
                if social['type'] == type_social:
                    return social['url']
        return socials
    
    def get_deep_information(self, token_address: str):
        url = f'https://api.dexscreener.com/latest/dex/tokens/{token_address}'
        response = requests.get(url)
        if response.status_code == 200 and response:
            response = response.json()
            if response['pairs'] is not None:
                pair = response['pairs'][0]
                return pair
        return {}
    
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
    
    
    API_KEY = os.environ['API_KEY']
    API_SECRET_KEY = os.environ['API_SECRET_KEY']
    ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
    ACCESS_TOKEN_SECRET = os.environ['ACCESS_TOKEN_SECRET']
    BEARER_TOKEN = os.environ["BEARER_TOKEN"]
    CLIENT_ID = os.environ["CLIENT_ID"]
    CLIENT_SECRET = os.environ["CLIENT_SECRET"]

    #define object
    fetcher = SolanaTransactionFetcher()
    x_client_post = XClient(
        bearer_token= BEARER_TOKEN,
        consumer_key= API_KEY,
        consumer_secret= API_SECRET_KEY,
        access_token= ACCESS_TOKEN,
        access_token_secret= ACCESS_TOKEN_SECRET
    )
    # Usage example (replace with actual API key and host):
    
    x_client = TwitterApiClient(os.environ.get("RAPIDAPI_KEY",""),os.environ.get("RAPIDAPI_HOST",""))
    reporter = Reporter()
    
    # coin information
    result = fetcher.get_coin(page_start = 700, num_page = 20, page_size = 100)
    promise_token = result[0]
    tweet_username = promise_token['tweet_username']
    token_address = promise_token['address']
    token_name = promise_token['name']
    #  analyze narrative
     
    rest_id = x_client.get_user_by_username(tweet_username)
    print(rest_id)
    post_ids = x_client.get_posts_by_rest_id(rest_id)
    tweets = []
    for post_id in post_ids:
        tweets.append(x_client.get_post_content(post_id))
    print(tweets)
    texts = "\n".join(tweets).strip()

    trending_narrative = """Rebellion against the status quo: Hunger games, Oblivion, 12 Years a slave, in a world of complexity, ruled by dynamics which people feel are out of their direct control, rebellion is a theme that resonates deeply and generates powerful resonance."""
    analysis = reporter.analyse(trending_narrative, texts)

    #calculate score
    total_score, score_reasoning = fetcher.calculate_score(promise_token)
    
    report = reporter.make_report(token_name, ca = token_address, analyse =analysis, aisem_score= total_score )
    detail_score = reporter.make_clarify(score_reasoning)
    print(report)
    print(detail_score)
    if total_score>40:
        x_client_post.post(report, user_auth = True)

