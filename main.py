import os
import json
import requests
from pybit.unified_trading import HTTP

# Настройки из Secrets GitHub
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
THRESHOLD = 5.0  # Процент изменения (например, 5%)

session = HTTP(testnet=False)

def send_tg_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"})

def get_symbols():
    resp = session.get_instruments_info(category="linear")
    return [item['symbol'] for item in resp['result']['list'] if item['symbol'].endswith('USDT')]

def main():
    symbols = get_symbols()
    
    # Загружаем старые данные
    if os.path.exists("last_oi.json"):
        with open("last_oi.json", "r") as f:
            old_data = json.load(f)
    else:
        old_data = {}

    new_data = {}
    alerts = []

    print(f"Проверка {len(symbols)} тикеров...")

    for symbol in symbols:
        try:
            # Получаем текущий OI
            res = session.get_open_interest(category="linear", symbol=symbol, limit=1)
            current_oi = float(res['result']['list'][0]['openInterest'])
            new_data[symbol] = current_oi

            if symbol in old_data:
                prev_oi = old_data[symbol]
                if prev_oi == 0: continue
                
                change = ((current_oi - prev_oi) / prev_oi) * 100
                
                if abs(change) >= THRESHOLD:
                    emoji = "📈" if change > 0 else "📉"
                    alerts.append(f"{emoji} <b>{symbol}</b>\nИзменение OI: <code>{change:+.2f}%</code>")
        except:
            continue

    # Сохраняем новые данные для следующего запуска
    with open("last_oi.json", "w") as f:
        json.dump(new_data, f)

    # Если есть аномалии — шлем в ТГ
    if alerts:
        message = "<b>🚀 Аномалии Open Interest (Bybit):</b>\n\n" + "\n\n".join(alerts)
        send_tg_message(message)
    else:
        print("Аномалий не обнаружено.")

if __name__ == "__main__":
    main()
