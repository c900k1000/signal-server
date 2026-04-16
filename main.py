import os
import time
import re
import logging
logging.getLogger("uvicorn.access").disabled = True
from fastapi import FastAPI, Response, Request
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import uvicorn

# ================= 環境變數設定 =================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# 🔥🔥🔥 智能分流群組配置 🔥🔥🔥
GROUP_CONFIG = {
    # 🏆 舊通道 (Render 網址專用，舊客戶維持黃金/BTC)
    -1002249680342: {"symbol": "XAUUSD", "channel": "legacy"},  
    -1003307050368: {"symbol": "BTCUSD", "channel": "legacy"},   
    
    # 🆕 新測試通道 (Cloudflare 網址專用)
    -1003006310733: {"symbol": "TESTING", "channel": "new"} 
}

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SECRET_PASS = os.environ.get("SECRET_PASS")
SIGNAL_TIMEOUT = 300 

app = FastAPI()

# 🔥 給大腦穿上偽裝衣
spy_client = TelegramClient(
    StringSession(SESSION_STRING), 
    API_ID, 
    API_HASH,
    device_model="iPhone 15 Pro Max",
    system_version="iOS 17.4.1",
    app_version="10.11.0"
)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# 📦 準備兩個完全獨立的訊號保險箱 (確保新舊訊號不串味)
signal_legacy = {
    "id": 0, "action": "", "symbol": "", "entry": 0.0, "sl": 0.0, 
    "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0
}
signal_new = {
    "id": 0, "action": "", "symbol": "", "entry": 0.0, "sl": 0.0, 
    "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0
}
handled_messages = set() 

# ================= A: 訊號解析邏輯 =================
def parse_signal(text, default_symbol):
    text = text.upper()
    data = {
        "action": "", "symbol": default_symbol,
        "entry": 0.0, "sl": 0.0,
        "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0
    }
    
    # 判斷動作
    if "BUY" in text or "做多" in text: data["action"] = "buy"
    elif "SELL" in text or "做空" in text: data["action"] = "sell"
    elif "CLOSE" in text: data["action"] = "close_all"
    
    if not data["action"]: return None
    
    # 關鍵：從文字中精準抓取商品名稱 (例如 XAUUSD 或 BTCUSD)
    # 如果文字裡有寫，就蓋掉預設的 default_symbol
    symbol_match = re.search(r"(XAUUSD|BTCUSD|GOLD|BTC)", text)
    if symbol_match:
        found = symbol_match.group(1)
        if found in ["GOLD", "XAUUSD"]: data["symbol"] = "XAUUSD"
        elif found in ["BTC", "BTCUSD"]: data["symbol"] = "BTCUSD"
    
    # 解析 SL/TP
    sl_match = re.search(r"SL\D*(\d+(\.\d+)?)", text)
    if sl_match: data["sl"] = float(sl_match.group(1))
    
    for i in range(1, 5):
        tp_key = f"tp{i}"
        tp_match = re.search(rf"TP{i}\D*(\d+(\.\d+)?)", text)
        if tp_match: data[tp_key] = float(tp_match.group(1))
            
    return data

@spy_client.on(events.NewMessage())
async def spy_handler(event):
    incoming_id = event.chat_id
    if incoming_id not in GROUP_CONFIG: return 
    
    config = GROUP_CONFIG[incoming_id]
    default_sym = config["symbol"]
    channel = config["channel"]

    print(f"✅ 收到 [{channel} 通道] 原始訊息內容: {event.raw_text}")
    
    result = parse_signal(event.raw_text, default_sym)
    if result and result["action"]:
        # 🔑 決定要存進哪一個訊號保險箱
        target_signal = signal_legacy if channel == "legacy" else signal_new
        
        target_signal.update({
            "id": int(time.time() * 1000),
            "action": result["action"],
            "symbol": result["symbol"],
            "sl": result["sl"],
            "tp1": result["tp1"],
            "tp2": result["tp2"],
            "tp3": result["tp3"],
            "tp4": result["tp4"]
        })
        print(f"🚀 訊號已鎖定 ({channel}): {result['symbol']} {result['action']} | TP1:{result['tp1']}")

# ================= B: 發貨機器人邏輯 =================
@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not event.is_private: return
    sender = await event.get_sender()
    await event.respond(f"👋 您好 {sender.first_name}！\n請輸入密碼以獲取檔案。")

@bot_client.on(events.NewMessage(incoming=True)) 
async def password_check(event):
    if not event.is_private or event.text.startswith('/'): return
    if event.id in handled_messages: return
    handled_messages.add(event.id)
    if len(handled_messages) > 100: handled_messages.pop(0)
    
    msg = event.text.strip()
    if msg == SECRET_PASS:
        await event.respond("✅ 密碼正確！正在發送檔案...")
        files = ['EA.ex5', '使用教學.pdf'] 
        existing_files = [f for f in files if os.path.exists(f)]
        if existing_files:
            await event.respond("🎁 這是您的檔案：", file=existing_files)
    elif msg not in ["密碼", "發送", "檔案"]:
        await event.respond("❌ 密碼錯誤")

# ================= C: 智能交通警察 (API 路由) =================
@app.get("/check_signal")
async def check_signal(request: Request, response: Response):
    # 🕵️ 辨識來者的「網址車牌」
    host = request.headers.get("host", "")
    
    # 如果是從 Cloudflare 網址過來的 (新測試客戶)
    if "goldbrother-api.xyz" in host:
        # 開啟 CF 1 秒快取，保護 Render 流量
        response.headers["Cache-Control"] = "public, max-age=1"
        current = signal_new
    else:
        # 如果是從舊 Render 網址過來的 (舊客戶)
        # 不開快取，提供舊的黃金/BTC 訊號
        current = signal_legacy

    now = int(time.time() * 1000)
    if (now - current["id"]) > (SIGNAL_TIMEOUT * 1000):
        return {"has_signal": False, "data": {"id": current["id"], "action": "", "symbol": "", "tp1": 0, "tp4": 0}}
    return {"has_signal": True, "data": current}

@app.on_event("startup")
async def startup_event():
    await spy_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    print("========================================")
    print(f"✅ 雙核心分流系統啟動！")
    print(f"🚗 舊通道網址: xxx.onrender.com (監聽舊群)")
    print(f"🚙 新通道網址: api.goldbrother-api.xyz (監聽測試群)")
    print("========================================")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, access_log=False)
