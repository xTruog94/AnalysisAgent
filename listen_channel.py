from telethon import TelegramClient, events
import pika
import json

# Your API credentials
API_ID = '21451416'
API_HASH = 'c4eecd06ec1f1dfbae429a397b182bd3'
CHANNEL_USERNAME = 'SolanaListing'  # e.g., 'examplechannel'

# Create a client instance
client = TelegramClient('session_name', API_ID, API_HASH)
QUEUE_NAME = 'test_messages'
RBMQ_HOST="42.96.32.131"
RBMQ_PORT=5678
RBMQ_USER_NAME="root"
RBMQ_PASSWORD="LibgSsr4399K"

def setup_rabbitmq():
    credentials = pika.PlainCredentials(RBMQ_USER_NAME, RBMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RBMQ_HOST,
        port=RBMQ_PORT,
        virtual_host="/",
        credentials=credentials,
        connection_attempts=3,
        retry_delay=5,
        heartbeat= 6000
    )
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    return connection, channel

# Function to push message to RabbitMQ
def push_to_rabbitmq(channel, message):
    try:
        channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
        )
        print(f" RabbitMQ: {message}")
    except Exception as e:
        print(f"Failed to push message to RabbitMQ: {e}")

@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
async def new_message_listener(event):
    # Print the message text
    print(f"New message in {CHANNEL_USERNAME}: {event.text}")
    if "New OpenBook Detected" not in event.text:
        message_data = {
            "message_id": event.message.id,
            "text": event.message.message,
            "sender_id": event.message.sender_id,
            "date": str(event.message.date)
        }
        push_to_rabbitmq(rabbitmq_channel, message_data)
        
async def main():
    print("Listening to messages...")
    
    await client.run_until_disconnected()
    
    
rabbitmq_connection, rabbitmq_channel = setup_rabbitmq()
# Start the client and listen for messages
client.start()
client.loop.run_until_complete(main())




