import os
import time
import re
from fastapi import FastAPI
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import uvicorn

# ================= 環境變數設定 =================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
# 建議把這行打開，只監聽特定群組，避免誤觸
TARGET_GROUP_ID = int(os.environ.get("GROUP_ID")) 

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SECRET_PASS = os.environ.get("SECRET_PASS")

app = FastAPI()

# 雙核心啟動：間諜 (聽訊號) + 機器人 (客服發貨)
spy_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# 訊號結構擴充：包含 tp1 ~ tp4
current_signal = {
    "id": 0, "action": "", "symbol": "", "entry": 0.0, "sl": 0.0, 
    "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0
}

# ================= A: 間諜監聽邏輯 =================
def parse_signal(text):
    text = text.upper()
    data = {
        "action": "", "symbol": "XAUUSD", "entry": 0.0, "sl": 0.0,
        "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0
    }
    
    # 1. 判斷方向
    if "BUY" in text or "做多" in text: data["action"] = "buy"
    elif "SELL" in text or "做空" in text: data["action"] = "sell"
    elif "CLOSE" in text: data["action"] = "close_all"
    
    if not data["action"]: return None
    
    # 2. 判斷商品
    entry_match = re.search(r"(BUY|SELL)\s+([A-Z0-9]+)", text)
    if entry_match: data["symbol"] = entry_match.group(2)
    
    # 3. 判斷 SL
    sl_match = re.search(r"SL\D*(\d+(\.\d+)?)", text)
    if sl_match: data["sl"] = float(sl_match.group(1))
    
    # 4. 判斷 TP1 ~ TP4
    for i in range(1, 5):
        tp_key = f"tp{i}"
        tp_match = re.search(rf"TP{i}\D*(\d+(\.\d+)?)", text)
        if tp_match: 
            data[tp_key] = float(tp_match.group(1))
            
    return data

@spy_client.on(events.NewMessage())
async def spy_handler(event):
    # 過濾群組 (建議開啟)
    if TARGET_GROUP_ID and event.chat_id != TARGET_GROUP_ID: return

    text = event.raw_text
    result = parse_signal(text)
    
    if result and result["action"]:
        current_signal["id"] = int(time.time() * 1000)
        current_signal["action"] = result["action"]
        current_signal["symbol"] = result["symbol"]
        current_signal["sl"] = result["sl"]
        # 分別更新 TP1~TP4
        current_signal["tp1"] = result["tp1"]
        current_signal["tp2"] = result["tp2"]
        current_signal["tp3"] = result["tp3"]
        current_signal["tp4"] = result["tp4"]
        
        print(f"🚀 廣播訊號: {result['symbol']} {result['action']} | TP1:{result['tp1']} ... TP4:{result['tp4']}")

# ================= B: 發貨機器人邏輯 (三重防護版) =================

handled_messages = set() # 去重紀錄

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not event.is_private: return
    sender = await event.get_sender()
    await event.respond(f"👋 您好 {sender.first_name}！\n請輸入 **領取密碼** 以獲取最新 EA。")

@bot_client.on(events.NewMessage(incoming=True)) 
async def password_check(event):
    if not event.is_private or event.text.startswith('/'): return

    # 去重檢查
    if event.id in handled_messages: return
    handled_messages.add(event.id)
    if len(handled_messages) > 100: handled_messages.pop()

    # 自我對話檢查
    me = await bot_client.get_me()
    sender = await event.get_sender()
    if sender.id == me.id: return

    msg = event.text.strip()
    # 關鍵字防護
    if "密碼" in msg or "發送" in msg or "檔案" in msg: return

    if msg == SECRET_PASS:
        await event.respond("✅ 密碼正確！正在發送檔案...")
        
        # ⚠️ 請確保 GitHub 上有這兩個檔案，檔名要一模一樣
        files = ['EA.ex5', '使用教學.pdf'] 
        existing_files = [f for f in files if os.path.exists(f)]

        if existing_files:
            try:
                await event.respond("🎁 這是您的檔案：", file=existing_files)
                print(f"✅ 發貨給: {sender.id}")
            except Exception as e:
                await event.respond(f"❌ 發送失敗: {str(e)}")
        else:
            await event.respond("❌ 系統錯誤：找不到檔案，請聯繫管理員補檔。")
            
    else:
        await event.respond("❌ 密碼錯誤，請重新輸入。")

# ================= 系統啟動 =================
@app.on_event("startup")
async def startup_event():
    await spy_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ 系統全開 (監聽 + 發貨機器人)")

@app.get("/check_signal")
async def check_signal():
    return {"has_signal": True, "data": current_signal}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
