import os
import time
from fastapi import FastAPI
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import uvicorn

# 從雲端環境變數讀取設定 (安全！)
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
SOURCE_GROUP_ID = int(os.environ.get("GROUP_ID"))

app = FastAPI()

# 使用 StringSession 直接登入，不需要再輸入驗證碼
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

current_signal = {"id": 0, "action": "", "symbol": "XAUUSD"}

@client.on(events.NewMessage(chats=SOURCE_GROUP_ID))
async def handler(event):
    text = event.raw_text.lower()
    print(f"監聽中: {text}")
    
    action = ""
    # 這裡依照您群組機器人的格式修改
    if "buy" in text: action = "buy"
    elif "sell" in text: action = "sell"
    elif "close" in text: action = "close_all"
    
    if action:
        current_signal["id"] = int(time.time() * 1000)
        current_signal["action"] = action
        print(f"🚀 更新訊號: {action}")

@app.on_event("startup")
async def startup_event():
    await client.start()

@app.get("/check_signal")
async def check_signal():
    return {"has_signal": True, "data": current_signal}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
