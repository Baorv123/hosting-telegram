import telebot
import requests
import re
import time
import threading
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException
import os

TOKEN = "7829538203:AAEFnmVi0jOhj6Mqf1OFVfErlvT7fVsG88E"
bot = telebot.TeleBot(TOKEN)

API_URL = "https://www.tikwm.com/api/"

# --- RESET LOG THEO THÁNG ---
def reset_log_if_new_month():
    current_month = datetime.now().strftime("%m")
    if not os.path.exists("log_meta.txt"):
        with open("log_meta.txt", "w") as f:
            f.write(current_month)
        return
    with open("log_meta.txt", "r") as f:
        last_month = f.read().strip()
    if current_month != last_month:
        # Reset log
        with open("log.txt", "w") as f:
            f.write("")
        with open("log_meta.txt", "w") as f:
            f.write(current_month)

reset_log_if_new_month()

# --- GHI LOG VIDEO ---
def get_log_index():
    try:
        with open("log.txt", "r", encoding="utf-8") as f:
            return len(f.readlines()) + 1
    except FileNotFoundError:
        return 1

# --- GHI DANH SÁCH TIN NHẮN SẼ XOÁ SAU 1 NGÀY ---
def save_message_for_deletion(chat_id, message_id):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("delete_queue.txt", "a", encoding="utf-8") as f:
        f.write(f"{chat_id}|{message_id}|{timestamp}\n")

# --- VÒNG LẶP XOÁ TIN NHẮN MỖI 10 PHÚT ---
def deletion_worker():
    while True:
        try:
            lines_to_keep = []
            if os.path.exists("delete_queue.txt"):
                with open("delete_queue.txt", "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line in lines:
                    parts = line.strip().split("|")
                    if len(parts) != 3:
                        continue
                    chat_id, message_id, timestamp_str = parts
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    if datetime.now() - timestamp >= timedelta(days=1):
                        try:
                            bot.delete_message(int(chat_id), int(message_id))
                        except:
                            pass
                    else:
                        lines_to_keep.append(line)

                with open("delete_queue.txt", "w", encoding="utf-8") as f:
                    f.writelines(lines_to_keep)
        except Exception as e:
            print(f"[XÓA TỰ ĐỘNG] Lỗi: {e}")

        time.sleep(600)  # 10 phút

# --- XỬ LÝ LỆNH ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🎬 Gửi link TikTok hoặc dùng /tiktok <link> để tải video không logo.\nTham Gia Nhóm Giao Lưu Vui Vẻ https://t.me/+DGXr9rnBo_E2MTdl.")

@bot.message_handler(commands=['tiktok'])
def tiktok_info(message):
    args = message.text.split(" ", 1)
    if len(args) < 2:
        bot.reply_to(message, "❗ Vui lòng gửi link TikTok sau lệnh /tiktok")
        return
    url = args[1]
    save_message_for_deletion(message.chat.id, message.message_id)
    handle_tiktok_link(message, url)

@bot.message_handler(func=lambda message: True)
def detect_link(message):
    if not message.text:
        return
    urls = re.findall(r'(https?://[^\s]+)', message.text)
    for url in urls:
        if "tiktok.com" in url:
            save_message_for_deletion(message.chat.id, message.message_id)
            handle_tiktok_link(message, url)
            return

def handle_tiktok_link(message, url):
    try:
        params = {'url': url}
        response = requests.get(API_URL, params=params).json()
        if response.get("code") != 0:
            bot.reply_to(message, "⚠️ Không thể lấy dữ liệu từ liên kết.")
            return

        data = response["data"]
        video_url = data.get("play")
        music_url = data.get("music", "")
        nickname = data.get("nickname", "").strip()
        unique_id = data.get("unique_id", "").strip()

        nickname_display = nickname if nickname else "Không rõ"
        unique_id_display = f"@{unique_id}" if unique_id else ""
        caption = f"👤 {nickname_display} ({unique_id_display})\n🎵 Nhạc nền: bấm nút dưới 👇"

        markup = InlineKeyboardMarkup()
        if music_url.startswith("http"):
            markup.add(
                InlineKeyboardButton("🎵 LINK NHẠC", url=music_url),
                InlineKeyboardButton("👤 ADMIN", url="https://t.me/gb211ad")
            )

        if video_url:
            while True:
                try:
                    bot.send_video(message.chat.id, video_url, caption=caption, reply_markup=markup)
                    log_index = get_log_index()
                    with open("log.txt", "a", encoding="utf-8") as f:
                        f.write(f"[{log_index}] [{time.strftime('%Y-%m-%d %H:%M:%S')}] {message.from_user.id} - {message.from_user.first_name}: {url}\n")
                    break
                except ApiTelegramException as e:
                    if "Too Many Requests" in str(e):
                        retry_after = 30
                        try:
                            retry_after = int(str(e).split("retry after")[1].split('"')[0])
                        except:
                            pass
                        bot.send_message(message.chat.id, f"🕒 Bị giới hạn gửi video, đợi {retry_after} giây...")
                        time.sleep(retry_after + 1)
                    else:
                        bot.send_message(message.chat.id, f"❌ Lỗi khi gửi video: {e}")
                        break
        else:
            bot.reply_to(message, "❌ Không tìm thấy video.")
    except Exception as e:
        bot.reply_to(message, f"💥 Lỗi: {e}")

# --- KHỞI ĐỘNG VÒNG XOÁ TỰ ĐỘNG ---
threading.Thread(target=deletion_worker, daemon=True).start()

print("[Bot] Đang chạy...")
bot.polling(none_stop=True, interval=0)