import os
import time
import re
from fastapi import FastAPI
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import uvicorn

# ================= 環境變數 =================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
# TARGET_GROUP_ID = int(os.environ.get("GROUP_ID")) 

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SECRET_PASS = os.environ.get("SECRET_PASS")

app = FastAPI()

# 雙核心啟動
spy_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

current_signal = {"id": 0, "action": "", "symbol": "", "entry": 0.0, "sl": 0.0, "tp": 0.0}

# ================= A: 間諜邏輯 (不變) =================
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
        if tp_match: data["tp"] = float(tp_match.group(1)); break
    return data

@spy_client.on(events.NewMessage())
async def spy_handler(event):
    text = event.raw_text
    result = parse_signal(text)
    if result and result["action"]:
        current_signal["id"] = int(time.time() * 1000)
        current_signal["action"] = result["action"]
        current_signal["symbol"] = result["symbol"]
        current_signal["sl"] = result["sl"]
        current_signal["tp"] = result["tp"]
        print(f"🚀 廣播: {result['symbol']} {result['action']}")

# ================= B: 機器人邏輯 (核彈級防護版) =================

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not event.is_private: return
    sender = await event.get_sender()
    await event.respond(f"👋 您好 {sender.first_name}！\n請輸入 **領取密碼**。")

@bot_client.on(events.NewMessage())
async def password_check(event):
    # 1. 第一層防護：只在私訊運作，且忽略指令
    if not event.is_private or event.text.startswith('/'): return

    # 2. 第二層防護：確保發話者不是機器人自己 (這最重要！)
    me = await bot_client.get_me()
    sender = await event.get_sender()
    if sender.id == me.id:
        return # 如果是我自己講話，立刻閉嘴

    msg = event.text.strip()

    # 3. 第三層防護 (邏輯鎖)：如果訊息內容包含機器人的回話關鍵字，強制忽略
    if "密碼錯誤" in msg or "密碼正確" in msg or "發送失敗" in msg:
        print(f"🛡️ 觸發防護，忽略訊息: {msg}")
        return

    # === 驗證邏輯 ===
    if msg == SECRET_PASS:
        await event.respond("✅ 密碼正確！正在發送檔案...")
        
        # 檔案清單 (請確認 GitHub 有這些檔案)
        files = ['EA.ex5', '使用教學.docx']
        existing_files = [f for f in files if os.path.exists(f)]

        if existing_files:
            try:
                await event.respond("🎁 檔案如下：", file=existing_files)
                print(f"✅ 發貨成功: {sender.id}")
            except Exception as e:
                await event.respond(f"❌ 發送失敗: {str(e)}")
        else:
            await event.respond("❌ 錯誤：找不到檔案，請通知管理員補檔。")
            print("❌ 找不到檔案，請檢查 GitHub 檔名是否正確")
            
    else:
        # 只有當真的輸入錯誤時才回覆
        await event.respond("❌ 密碼錯誤，請重新輸入，或聯繫管理員購買。")

# ================= 啟動區 =================
@app.on_event("startup")
async def startup_event():
    await spy_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ 系統啟動 (已開啟三重迴圈防護)")

@app.get("/check_signal")
async def check_signal():
    return {"has_signal": True, "data": current_signal}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
