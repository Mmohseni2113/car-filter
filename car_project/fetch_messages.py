# fetch_messages.py
from telethon import TelegramClient

api_id = 27102606
api_hash = '0f30bd68dd04a80188d8f1776735c1e3'
channels = ['autokhass', 'tamasha_car', 'sourenacars']

client = TelegramClient('session_name', api_id, api_hash)

async def fetch_messages():
    await client.start(phone='YOUR_PHONE_NUMBER')  # شماره خودت (مثل +989123456789)
    with open('messages.txt', 'w', encoding='utf-8') as f:
        for channel in channels:
            try:
                entity = await client.get_entity(channel)
                async for message in client.iter_messages(entity, limit=200):
                    if message.text:
                        f.write(f"{channel}||{message.text}\n")
            except Exception as e:
                print(f"خطا در کانال {channel}: {e}")

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(fetch_messages())