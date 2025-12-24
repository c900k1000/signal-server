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
# TARGET_GROUP_ID = int(os.environ.get("GROUP_ID")) # 如果不需要過濾群組可註解

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SECRET_PASS = os.environ.get("SECRET_PASS")

app = FastAPI()

# 1. 間諜客戶端
spy_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# 2. 機器人客戶端
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

current_signal = {
    "id": 0, "action": "", "symbol": "", "entry": 0.0, "sl": 0.0, "tp": 0.0
}

# ================= A: 間諜邏輯 (保持不變) =================
def parse_signal(text):
    text = text.upper()
    data = {"action": "", "symbol": "XAUUSD", "entry": 0.0, "sl": 0.0, "tp": 0.0}
    
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
    text = event.raw_text
    # print(f"🕵️ 間諜收到: {text[:30]}...") # 除錯用
    result = parse_signal(text)
    if result and result["action"]:
        current_signal["id"] = int(time.time() * 1000)
        current_signal["action"] = result["action"]
        current_signal["symbol"] = result["symbol"]
        current_signal["sl"] = result["sl"]
        current_signal["tp"] = result["tp"]
        print(f"🚀 廣播: {result['symbol']} {result['action']}")

# ================= B: 機器人邏輯 (修復版) =================

# 1. 只回應私訊 (/start)
@bot_client.on(events.NewMessage(pattern='/start', incoming=True))
async def start_handler(event):
    if not event.is_private: return # 不在群組回應
    
    sender = await event.get_sender()
    await event.respond(
        f"👋 您好 {sender.first_name}！\n"
        "請輸入 **領取密碼** 以獲得 EA 及說明書。"
    )

# 2. 密碼檢查 (加入 incoming=True 防止自問自答)
@bot_client.on(events.NewMessage(incoming=True)) 
async def password_check(event):
    # 只在私訊運作，且忽略指令
    if not event.is_private or event.text.startswith('/'): return
    
    user_input = event.text.strip()
    
    if user_input == SECRET_PASS:
        await event.respond("✅ 密碼正確！正在發送檔案...")
        
        # 定義要發送的檔案名稱 (請確認 GitHub 上檔名一模一樣)
        files_to_send = ['EA.ex5', '使用教學.docx'] 
        
        # 檢查檔案是否存在，避免報錯
        existing_files = [f for f in files_to_send if os.path.exists(f)]
        
        if existing_files:
            try:
                await event.respond(
                    "🎁 這是您的檔案：",
                    file=existing_files
                )
                print(f"✅ 已發貨給: {event.sender_id}")
            except Exception as e:
                await event.respond(f"❌ 發送失敗: {str(e)}")
        else:
            await event.respond("❌ 系統錯誤：找不到檔案，請聯繫管理員補檔。")
            print(f"❌ 找不到檔案: {files_to_send}")
            
    else:
        # 只有在用戶輸入錯誤密碼時才回覆，而且不會觸發迴圈
        await event.respond("❌ 密碼錯誤，請重新輸入。")

# ================= 啟動區 =================
@app.on_event("startup")
async def startup_event():
    await spy_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ 系統全開：間諜監聽中 + 機器人待命中")

@app.get("/check_signal")
async def check_signal():
    return {"has_signal": True, "data": current_signal}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
