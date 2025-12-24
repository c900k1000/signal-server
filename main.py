import os
import time
import re
from fastapi import FastAPI
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import uvicorn

# ================= 設定區 =================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
TARGET_GROUP_ID = int(os.environ.get("GROUP_ID")) 

app = FastAPI()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# 訊號結構
current_signal = {
    "id": 0,
    "action": "",
    "symbol": "",      
    "entry": 0.0,
    "sl": 0.0,
    "tp": 0.0
}

# ================= 解析邏輯 =================
def parse_signal(text):
    text = text.upper()
    data = {"action": "", "symbol": "", "entry": 0.0, "sl": 0.0, "tp": 0.0}
    
    # 1. 抓取方向
    if "BUY" in text or "做多" in text: data["action"] = "buy"
    elif "SELL" in text or "做空" in text: data["action"] = "sell"
    elif "CLOSE" in text or "平倉" in text: data["action"] = "close_all"
    
    if not data["action"]: return None

    # 2. 抓取商品 (Symbol)
    # 邏輯: 尋找 "SELL XAUUSD" 或 "BUY EURUSD"
    # 我們這裡稍微放寬一點，只要有 [英文+數字] 跟在動作後面就抓
    entry_match = re.search(r"(BUY|SELL)\s+([A-Z0-9]+)", text)
    
    if entry_match:
        data["symbol"] = entry_match.group(2) # 例如 XAUUSD
    else:
        data["symbol"] = "XAUUSD" # 預設值

    # 3. 抓取 SL (止損)
    sl_match = re.search(r"SL\D*(\d+(\.\d+)?)", text)
    if sl_match: data["sl"] = float(sl_match.group(1))

    # 4. 抓取 TP (優先抓 TP4)
    for i in range(4, 0, -1):
        tp_match = re.search(rf"TP{i}\D*(\d+(\.\d+)?)", text)
        if tp_match:
            data["tp"] = float(tp_match.group(1))
            break 
            
    return data

@client.on(events.NewMessage())
async def handler(event):
    # if event.chat_id != TARGET_GROUP_ID: return # 正式上線請打開這行

    text = event.raw_text
    print(f"收到訊號: {text}")
    
    result = parse_signal(text)
    
    # 只要有動作就廣播 (不需要檢查 entry 價格了，因為我們是市價進場)
    if result and result["action"]: 
        current_signal["id"] = int(time.time() * 1000)
        current_signal["action"] = result["action"]
        current_signal["symbol"] = result["symbol"]
        current_signal["sl"] = result["sl"]
        current_signal["tp"] = result["tp"]
        
        print(f"🚀 市價單訊號: {result['symbol']} {result['action']} | SL:{result['sl']} TP:{result['tp']}")

@app.on_event("startup")
async def startup_event():
    await client.start()

@app.get("/check_signal")
async def check_signal():
    return {"has_signal": True, "data": current_signal}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
