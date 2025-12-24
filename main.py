import os
import time
import re
import asyncio
from fastapi import FastAPI
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import uvicorn

# ================= 環境變數讀取 =================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
TARGET_GROUP_ID = int(os.environ.get("GROUP_ID")) 

# 👇 新增：機器人設定
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # 這是機器人的 Token
SECRET_PASS = os.environ.get("SECRET_PASS") # 這是您設定的領取密碼

app = FastAPI()

# 1. 建立「間諜」客戶端 (原本的)
spy_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# 2. 建立「櫃台機器人」客戶端 (新的)
# 注意：這裡我們不需要 session string，直接用 bot_token 登入
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# 訊號暫存
current_signal = {
    "id": 0, "action": "", "symbol": "", "sl": 0.0, "tp": 0.0
}

# ==========================================
# 🕵️‍♂️ A部分：間諜監聽邏輯 (原本的功能)
# ==========================================
# ... (這裡保留原本的解析邏輯 parse_signal 函式) ...
def parse_signal(text):
    text = text.upper()
    data = {"action": "", "symbol": "XAUUSD", "sl": 0.0, "tp": 0.0}
    if "BUY" in text or "做多" in text: data["action"] = "buy"
    elif "SELL" in text or "做空" in text: data["action"] = "sell"
    elif "CLOSE" in text: data["action"] = "close_all"
    
    if not data["action"]: return None
    
    entry_match = re.search(r"(BUY|SELL)\s+([A-Z0-9]+)", text)
    if entry_match: data["symbol"] = entry_match.group(2)
    
    sl_match = re.search(r"SL\D*(\d+(\.\d+)?)", text)
    if sl_match: data["sl"] = float(sl_match.group(1))
    
    for i in range(4, 0, -1):
        tp_match = re.search(rf"TP{i}\D*(\d+(\.\d+)?)", text)
        if tp_match: 
            data["tp"] = float(tp_match.group(1)); break
    return data

@spy_client.on(events.NewMessage())
async def spy_handler(event):
    # if event.chat_id != TARGET_GROUP_ID: return
    text = event.raw_text
    print(f"🕵️ 間諜收到: {text[:30]}...")
    result = parse_signal(text)
    if result and result["action"]:
        current_signal["id"] = int(time.time() * 1000)
        current_signal["action"] = result["action"]
        current_signal["symbol"] = result["symbol"]
        current_signal["sl"] = result["sl"]
        current_signal["tp"] = result["tp"]
        print(f"🚀 廣播: {result['symbol']} {result['action']}")

# ==========================================
# 🤖 B部分：櫃台機器人邏輯 (新功能)
# ==========================================

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    # 當用戶點擊「開始」時
    sender = await event.get_sender()
    welcome_msg = (
        f"👋 您好 {sender.first_name}！\n\n"
        "我是博士寶的自動發貨機器人。\n"
        "如果您已購買 EA，**請直接輸入「領取密碼」**。\n\n"
        "驗證成功後，我會自動將 EA 及說明書傳送給您。"
    )
    await event.respond(welcome_msg)

@bot_client.on(events.NewMessage())
async def password_check(event):
    # 忽略 /start 指令，避免重複
    if event.text.startswith('/'): return
    
    user_input = event.text.strip() # 去除前後空白
    
    # 檢查密碼是否正確
    if user_input == SECRET_PASS:
        await event.respond("✅ 密碼正確！正在發送檔案，請稍候...")
        
        try:
            # 傳送檔案 (必須確保這些檔案在 GitHub 上)
            # allow_cache=False 強制重新讀取檔案
            await event.respond(
                "🎁 這是您的 EA 與使用說明：\n請按照說明書進行安裝。",
                file=['EA.ex5', '使用教學.docx'] 
            )
            print(f"✅ 已發貨給用戶: {event.sender_id}")
            
        except Exception as e:
            await event.respond(f"❌ 發送失敗，請聯繫管理員。\n錯誤: {str(e)}")
            print(f"❌ 發貨錯誤: {e}")
            
    else:
        # 密碼錯誤
        await event.respond("❌ 密碼錯誤，請檢查後重新輸入，或聯繫管理員購買。")

# ================= 啟動區 =================
@app.on_event("startup")
async def startup_event():
    # 同時啟動兩個客戶端
    await spy_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ 間諜與發貨機器人皆已啟動！")

@app.get("/check_signal")
async def check_signal():
    return {"has_signal": True, "data": current_signal}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


