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
# 目標群組 ID (建議填入，只監聽特定群組)
TARGET_GROUP_ID = int(os.environ.get("GROUP_ID")) 

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SECRET_PASS = os.environ.get("SECRET_PASS")

# 🔥 設定訊號有效時間 (秒) - 超過 5 分鐘的訊號視為過期
SIGNAL_TIMEOUT = 300 

app = FastAPI()

# 雙核心啟動
spy_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# 訊號結構
current_signal = {
    "id": 0, "action": "", "symbol": "", "entry": 0.0, "sl": 0.0, 
    "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0
}

# 📒 授權帳本 (結構: { "tg_user_id": "mt5_account" })
# 注意：Render 重啟後會清空，若需永久保存需接資料庫，目前為記憶體暫存
authorized_users = {}

# ================= A: 間諜監聽邏輯 (解析 TP1-TP4) =================
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
    # 過濾群組
    if TARGET_GROUP_ID and event.chat_id != TARGET_GROUP_ID: return

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
        
        print(f"🚀 廣播訊號: {result['symbol']} {result['action']} | TP1:{result['tp1']} ... TP4:{result['tp4']}")

# ================= B: 發貨機器人 + 綁定邏輯 =================

handled_messages = set() # 去重紀錄

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not event.is_private: return
    sender = await event.get_sender()
    msg = (
        f"👋 您好 {sender.first_name}！\n\n"
        "1️⃣ 輸入 **領取密碼**：獲取 EA 檔案。\n"
        "2️⃣ 輸入 **/bind 帳號**：綁定 MT5 帳號 (例如: `/bind 66008822`)"
    )
    await event.respond(msg)

# --- 新增：帳號綁定功能 ---
@bot_client.on(events.NewMessage(pattern='/bind'))
async def bind_handler(event):
    if not event.is_private: return
    sender_id = str(event.sender_id)
    text = event.text.strip().split()
    
    if len(text) < 2:
        await event.respond("❌ 格式錯誤！請輸入：`/bind 您的MT5帳號`")
        return

    mt5_account = text[1]
    authorized_users[sender_id] = mt5_account
    print(f"✅ 用戶 {sender_id} 綁定帳號: {mt5_account}")
    await event.respond(f"✅ 綁定成功！\n您的 Telegram 已連結 MT5 帳號 `{mt5_account}`。")

# --- 發貨與驗證邏輯 ---
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
    if "密碼" in msg or "發送" in msg or "檔案" in msg or "綁定" in msg: return

    if msg == SECRET_PASS:
        await event.respond("✅ 密碼正確！正在發送檔案...")
        
        files = ['EA.ex5', '使用教學.pdf'] 
        existing_files = [f for f in files if os.path.exists(f)]

        if existing_files:
            try:
                await event.respond("🎁 這是您的檔案：\n(若需使用雲端授權，請輸入 /bind 帳號)", file=existing_files)
                print(f"✅ 發貨給: {sender.id}")
            except Exception as e:
                await event.respond(f"❌ 發送失敗: {str(e)}")
        else:
            await event.respond("❌ 系統錯誤：找不到檔案，請聯繫管理員補檔。")
            
    else:
        await event.respond("❌ 密碼錯誤，請重新輸入，或使用 /bind 指令。")

# ================= API 接口 (含超時判斷) =================

@app.get("/check_signal")
async def check_signal():
    # 🔥 關鍵修改：檢查訊號是否過期
    now = int(time.time() * 1000)
    signal_time = current_signal["id"]
    
    # 如果訊號產生超過 SIGNAL_TIMEOUT (例如 300秒)
    if (now - signal_time) > (SIGNAL_TIMEOUT * 1000):
        # 回傳空訊號，讓 EA 知道沒單可下
        return {
            "has_signal": False, 
            "data": {
                "id": current_signal["id"], 
                "action": "", # 清空動作
                "symbol": "",
                "tp1": 0, "tp4": 0
            }
        }

    return {"has_signal": True, "data": current_signal}

# 新增：雲端授權檢查接口 (配合 /bind 使用)
@app.get("/check_license")
async def check_license(account: str):
    all_allowed = list(authorized_users.values())
    # 這裡可以加入您的 VIP 白名單
    vip_accounts = ["50057009", "123456"] 
    
    if account in all_allowed or account in vip_accounts:
        return {"allowed": True}
    else:
        return {"allowed": False}

# ================= 系統啟動 =================
@app.on_event("startup")
async def startup_event():
    await spy_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ 系統全開 (監聽 + 發貨 + 雲端驗證 + 過期濾除)")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
