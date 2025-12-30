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

# 🔥 關鍵修正：直接把正確的 ID 寫死在這裡！
# 這樣機器人就只會聽這個群組，您跟朋友聊天它會自動忽略
TARGET_GROUP_ID = -3006310733

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SECRET_PASS = os.environ.get("SECRET_PASS")
SIGNAL_TIMEOUT = 300 

app = FastAPI()

spy_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

current_signal = {
    "id": 0, "action": "", "symbol": "", "entry": 0.0, "sl": 0.0, 
    "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0
}
authorized_users = {}

# ================= A: 間諜監聽邏輯 =================
def parse_signal(text):
    text = text.upper()
    data = {
        "action": "", "symbol": "XAUUSD", "entry": 0.0, "sl": 0.0,
        "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0
    }
    
    if "BUY" in text or "做多" in text: data["action"] = "buy"
    elif "SELL" in text or "做空" in text: data["action"] = "sell"
    elif "CLOSE" in text: data["action"] = "close_all"
    
    if not data["action"]: return None
    
    entry_match = re.search(r"(BUY|SELL)\s+([A-Z0-9]+)", text)
    if entry_match: data["symbol"] = entry_match.group(2)
    
    sl_match = re.search(r"SL\D*(\d+(\.\d+)?)", text)
    if sl_match: data["sl"] = float(sl_match.group(1))
    
    for i in range(1, 5):
        tp_key = f"tp{i}"
        tp_match = re.search(rf"TP{i}\D*(\d+(\.\d+)?)", text)
        if tp_match: data[tp_key] = float(tp_match.group(1))
            
    return data

@spy_client.on(events.NewMessage())
async def spy_handler(event):
    # 🔥 過濾器啟動：如果不是目標群組，直接忽略！
    if event.chat_id != TARGET_GROUP_ID:
        # print(f"忽略非目標訊息 ID: {event.chat_id}") # 若不想看雜訊 Logs 可註解掉
        return

    # 只有通過上面檢查的，才會執行下面這段
    print(f"👂 收到目標群組訊息！內容: {event.raw_text[:20]}...")
    
    text = event.raw_text
    result = parse_signal(text)
    
    if result and result["action"]:
        current_signal["id"] = int(time.time() * 1000)
        current_signal["action"] = result["action"]
        current_signal["symbol"] = result["symbol"]
        current_signal["sl"] = result["sl"]
        current_signal["tp1"] = result["tp1"]
        current_signal["tp2"] = result["tp2"]
        current_signal["tp3"] = result["tp3"]
        current_signal["tp4"] = result["tp4"]
        
        print(f"🚀 廣播訊號: {result['symbol']} {result['action']} | TP1:{result['tp1']} ...")

# ================= B: 發貨機器人 (維持不變) =================
handled_messages = set() 

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not event.is_private: return
    sender = await event.get_sender()
    await event.respond(f"👋 您好 {sender.first_name}！\n請輸入 **領取密碼** 或 **/bind 帳號**")

@bot_client.on(events.NewMessage(pattern='/bind'))
async def bind_handler(event):
    if not event.is_private: return
    text = event.text.strip().split()
    if len(text) < 2:
        await event.respond("❌ 格式錯誤！請輸入：`/bind 帳號`")
        return
    authorized_users[str(event.sender_id)] = text[1]
    await event.respond(f"✅ 綁定成功: {text[1]}")

@bot_client.on(events.NewMessage(incoming=True)) 
async def password_check(event):
    if not event.is_private or event.text.startswith('/'): return
    if event.id in handled_messages: return
    handled_messages.add(event.id)
    if len(handled_messages) > 100: handled_messages.pop()
    me = await bot_client.get_me()
    sender = await event.get_sender()
    if sender.id == me.id: return
    msg = event.text.strip()
    if "密碼" in msg or "發送" in msg or "檔案" in msg or "綁定" in msg: return

    if msg == SECRET_PASS:
        await event.respond("✅ 密碼正確！正在發送檔案...")
        files = ['EA.ex5', '使用教學.pdf'] 
        existing_files = [f for f in files if os.path.exists(f)]
        if existing_files:
            try:
                await event.respond("🎁 這是您的檔案：", file=existing_files)
            except Exception as e:
                await event.respond(f"❌ 發送失敗: {str(e)}")
        else:
            await event.respond("❌ 系統錯誤：找不到檔案")
    else:
        await event.respond("❌ 密碼錯誤")

@app.get("/check_signal")
async def check_signal():
    now = int(time.time() * 1000)
    signal_time = current_signal["id"]
    if (now - signal_time) > (SIGNAL_TIMEOUT * 1000):
        return {"has_signal": False, "data": {"id": current_signal["id"], "action": "", "symbol": "", "tp1": 0, "tp4": 0}}
    return {"has_signal": True, "data": current_signal}

@app.get("/check_license")
async def check_license(account: str):
    all_allowed = list(authorized_users.values())
    vip_accounts = ["50057009", "123456"] 
    if account in all_allowed or account in vip_accounts: return {"allowed": True}
    else: return {"allowed": False}

@app.on_event("startup")
async def startup_event():
    await spy_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print(f"✅ 系統啟動 | 鎖定監聽群組: {TARGET_GROUP_ID}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

