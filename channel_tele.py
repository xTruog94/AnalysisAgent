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
import pika
import json
from utils import parse_text_to_json

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
    
    def fetch_holder(self, address, coin_suppy, threshold = 0.25, num_page = 5, page_size = 40):
        """
        Fetch metadata for a given token address.
        """
        items = []
        tmp = {}
        for page_i in range(1, num_page+1):
            url = self.base_url + f"/token/holders?address={address}&page={page_i}&page_size={page_size}"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200 and response.json().get("success", False):
                tmp = response.json().get("data", {})
                items += tmp['items']
        total = tmp.get('total',0)
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
            
    def fetch_meta(self, token_info):
        """
        Fetch metadata for a given token address.
        """
        add = token_info['contract_address']
        coin_info = self.get_deep_information(add)
        coin_info = {**token_info, **coin_info}
        raw_info = copy.deepcopy(coin_info)
        if coin_info:
            volume_24 = coin_info.get('volume',{}).get('h24', 0)
            if add not in self.ignore_addresses:
                url = self.base_url + f"/token/meta?address={add}"
                response = requests.get(url, headers=self.headers)
                if response.status_code == 200 and response.json().get("success", False):
                    coin_info = response.json().get("data", {})
                
                tweet_username = None
                tweet = fetcher.get_social(coin_info['title'].split()[0], type_social = "twitter")
                if tweet and isinstance(tweet, str):
                    tweet_username = tweet.replace("https://x.com/","").replace("http://x.com/","")
                price_change = raw_info.get('priceChange',{}).get('h24', -100)
                if int(price_change) > -70:
                    coin_suppy = round(coin_info['supply'],0) if "supply" in coin_info else int(float(coin_info.get("total_supply",0).replace(",","")))
                    holders = self.fetch_holder(add, coin_suppy)
                    coin_info['holders'] = holders
                    coin_info['tweet_username'] = tweet_username
                    coin_info['volume_24h'] = volume_24
                    coin_info['txn_sell'] = raw_info.get("txns", {}).get("h24", {}).get("sells", 0)
                    coin_info['txn_buy'] = raw_info.get("txns", {}).get("h24", {}).get("buys", 0)
                    coin_info['price_change'] = price_change
        return coin_info
        
    def calculate_score(self, token_data : dict):
        scores = 0
        reasons = []
        # cộng điểm theo volume
        if token_data.get('volume_24h',0) > 1e6:
            score = 10
            reasons.append(f"- volume > 1M: {score} points")
            scores += score
         
        # txn
        if token_data.get('txn_sell',10000) < 1000:
            score = 10
            reasons.append(f"- txn_sell < 1000: {score} points")
            scores += score
        
        # txn
        if token_data.get('txn_sell',10000) < 1000:
            score = 10
            reasons.append(f"- txn_buy < 1000: {score} points")
            scores += score
        
        # top 10 holders < 16% 10 points
        try:
            top_10_holders = [int(x['amount']) for x in token_data['holders']['items']]
            total_top_10_holders = sum(top_10_holders)
            if total_top_10_holders < 0.16 * int(token_data.get('supply',1e6)):
                reasons.append(f"- total holders = {token_data['holders']['total']}: {score} points")
                scores += 10
            
            # Holder distribution đều dưới 1.8%
            top_10_holders = [int(x['amount']) for x in token_data['holders']['items']]
            if all([x < 0.018 * int(token_data.get('supply',1e6)) for x in top_10_holders]):
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
        except:
            reasons.append(f"- holder distribution < 1.8%: 10 points")
            scores += 0
        
        
        
        # price change 
        if token_data.get('price_change', -100) > -60:
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
                pair = response['pairs']
                if pair:
                    pair = pair[0]
                    socials = pair.get("info",{}).get("socials", [])
                else:
                    socials = {}
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




def connect_to_rabbitmq(host='localhost', port=5672, username='guest', password='guest', virtual_host='/'):
    # Connection parameters
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        virtual_host=virtual_host,
        credentials=credentials,
        connection_attempts=3,
        retry_delay=5
    )
    
    # Create connection
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    return connection, channel


def callback(ch, method, properties, body):
    # coin information
    message = json.loads(body.decode('utf8'))['text']
    token_info = parse_text_to_json(message)
    promise_token = fetcher.fetch_meta(token_info)
    tweet_username = promise_token.get('tweet_username', None)
    try:
        rest_id = x_client.get_user_by_username(tweet_username)
        post_ids = x_client.get_posts_by_rest_id(rest_id)
        tweets = []
        for post_id in post_ids:
            tweets.append(x_client.get_post_content(post_id))
        texts = "\n".join(tweets).strip()

        trending_narrative = """Rebellion against the status quo: Hunger games, Oblivion, 12 Years a slave, in a world of complexity, ruled by dynamics which people feel are out of their direct control, rebellion is a theme that resonates deeply and generates powerful resonance."""
        analysis = reporter.analyse(trending_narrative, texts)

        #calculate score
        total_score, score_reasoning = fetcher.calculate_score(promise_token)
        
        report = reporter.make_report(token_info['title'], ca = token_info['contract_address'], analyse =analysis, aisem_score= total_score )
        
        message = {
            "report": report,
            "detail": report
        }
        
        
        _ , sub_ch = connect_to_rabbitmq(
            host=os.environ.get("RBMQ_HOST",""),
            port=os.environ.get("RBMQ_PORT",""), 
            username=os.environ.get("RBMQ_USER_NAME",""), 
            password=os.environ.get("RBMQ_PASSWORD",""), 
            virtual_host='/'
        )
        sub_ch.queue_declare(queue='publish', durable = True)

        sub_ch.basic_publish(
                exchange='',
                routing_key="publish",
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
            )
        

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(e)
        ch.basic_ack(delivery_tag=method.delivery_tag)

if __name__ == "__main__":

    OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
    TELE_TOKEN = os.environ['TELE_TOKEN']
    TELE_GROUP_ID = os.environ['TELE_GROUP_ID']
    

    #define object
    fetcher = SolanaTransactionFetcher()
    
    x_client = TwitterApiClient(os.environ.get("RAPIDAPI_KEY",""),os.environ.get("RAPIDAPI_HOST",""))
    reporter = Reporter()
    
    
    
    # try:
    # Establish connection
    connection, channel = connect_to_rabbitmq(
        host=os.environ.get("RBMQ_HOST",""),
        port=os.environ.get("RBMQ_PORT",""), 
        username=os.environ.get("RBMQ_USER_NAME",""), 
        password=os.environ.get("RBMQ_PASSWORD",""), 
        virtual_host='/'
    )
    
    # Set up consumer
    channel.basic_consume(
        queue='test_messages',
        auto_ack=False,
        on_message_callback=callback,
    )
    
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()
        
    # except KeyboardInterrupt:
    #     print("Shutting down...")
    # except pika.exceptions.AMQPConnectionError as error:
    #     print(f"Connection error: {error}")
    # finally:
    #     print(1)
    #     if 'connection' in locals() and connection.is_open:
    #         connection.close()



