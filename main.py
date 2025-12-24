import os
import time
import re
from fastapi import FastAPI
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import uvicorn

# ================= 環境變數讀取 =================
# 這些變數會從 Render 的 Environment Variables 讀取
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
# 目標群組 ID (請確認 Render 上填寫的是 -100 開頭的整數)
TARGET_GROUP_ID = int(os.environ.get("GROUP_ID")) 

app = FastAPI()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# 訊號暫存區 (全域變數)
current_signal = {
    "id": 0,
    "action": "",
    "symbol": "XAUUSD",
    "sl": 0.0,
    "tp": 0.0,  # 這裡會存抓到的 TP4
    "msg": ""
}

# ================= 核心：文字解析邏輯 (Regex) =================
def parse_signal(text):
    text = text.lower() # 轉小寫方便比對
    data = {"action": "", "sl": 0.0, "tp": 0.0}
    
    # 1. 判斷方向
    if "buy" in text or "做多" in text:
        data["action"] = "buy"
    elif "sell" in text or "做空" in text:
        data["action"] = "sell"
    elif "close" in text or "平倉" in text:
        data["action"] = "close_all"

    # 如果沒抓到方向，就視為無效訊號
    if not data["action"]:
        return None

    # 2. 抓取止損 (SL)
    # 邏輯：尋找 "sl" 關鍵字，忽略中間的非數字字符，抓取後面的浮點數
    sl_match = re.search(r"sl\D*(\d+(\.\d+)?)", text)
    if sl_match:
        data["sl"] = float(sl_match.group(1))

    # 3. 抓取止盈 (優先順序: TP4 -> TP3 -> TP2 -> TP1)
    # 我們倒著找，先找 tp4，找到就停止
    for i in range(4, 0, -1):
        tp_key = f"tp{i}"
        tp_match = re.search(rf"{tp_key}\D*(\d+(\.\d+)?)", text)
        if tp_match:
            data["tp"] = float(tp_match.group(1))
            print(f"✅ 成功抓到 {tp_key}: {data['tp']}")
            break 
            
    return data

# ================= 監聽事件 =================
@client.on(events.NewMessage())
async def handler(event):
    # 過濾群組：只處理 TARGET_GROUP_ID 的訊息
    if event.chat_id != TARGET_GROUP_ID:
       # print(f"忽略非目標來源: {event.chat_id}")
       return

    text = event.raw_text
    print(f"🕵️ 收到訊號源 | ID: {event.chat_id} | 內容:\n{text}")
    
    # 呼叫解析函式
    result = parse_signal(text)
    
    if result:
        # 更新全域變數
        current_signal["id"] = int(time.time() * 1000)
        current_signal["action"] = result["action"]
        current_signal["sl"] = result["sl"]
        current_signal["tp"] = result["tp"]
        current_signal["msg"] = text[:50] # 紀錄前50字用於除錯
        
        print(f"🚀 廣播更新! 動作:{result['action']} | SL:{result['sl']} | TP:{result['tp']} (ID:{current_signal['id']})")

# ================= 系統啟動與 API =================
@app.on_event("startup")
async def startup_event():
    await client.start()
    print("✅ Telegram 監聽器已啟動，等待訊號...")

@app.get("/check_signal")
async def check_signal():
    return {"has_signal": True, "data": current_signal}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # 必須使用 uvicorn 啟動
    uvicorn.run(app, host="0.0.0.0", port=port)
