import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

# === 填入你剛才用手機申請到的資料 ===
API_ID = 39633568  # 請確認這是正確的 ID
API_HASH = '591be74a3776919b58058378425591f1'
# =================================

async def main():
    # 使用 async with 來確保資源正確釋放
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        print("------------------------------------------------------")
        print("請檢查您的 Telegram App (會收到官方發送的登入碼)")
        print("請在下方輸入您的手機號碼 (記得加國碼，如 +886912345678):")
        
        # 這裡會觸發登入流程
        await client.start()
        
        print("------------------------------------------------------")
        print("\n👇 請複製底下這串很長的亂碼 (這就是 SESSION_STRING)：\n")
        print(client.session.save())
        print("\n------------------------------------------------------")

if __name__ == "__main__":
    # 強制建立並執行事件迴圈，解決 Python 3.14 的報錯
    asyncio.run(main())
