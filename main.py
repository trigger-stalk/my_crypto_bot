import os
import requests
import json
import telebot
import time

# --- НАСТРОЙКИ ---
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OI_THRESHOLD = 5.0
DATA_FILE = "market_state.json"

bot = telebot.TeleBot(TG_TOKEN)

def get_bybit_tickers():
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    try:
        response = requests.get(url, timeout=15).json()
        if response.get('retCode') == 0:
            return {item['symbol']: item for item in response['result']['list'] if 'USDT' in item['symbol']}
    except Exception as e:
        print(f"Ошибка API Тикеров: {e}")
    return {}

def get_oi_for_symbol(symbol):
    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min"
    try:
        time.sleep(0.2) # Увеличили паузу для стабильности
        res = requests.get(url, timeout=15).json()
        if res.get('retCode') == 0 and res.get('result') and len(res['result']['list']) > 0:
            return float(res['result']['list'][0]['openInterest'])
    except Exception as e:
        print(f"Ошибка OI для {symbol}: {e}")
    return 0

def load_old_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                content = f.read()
                return json.loads(content) if content else {}
        except Exception as e:
            print(f"Ошибка чтения файла: {e}")
    return {}

def main():
    if not TG_TOKEN or not CHAT_ID:
        print("Критическая ошибка: Секреты (Tokens) не найдены!")
        return # Выход без ошибки 1

    print("Сканирование рынка...")
    tickers = get_bybit_tickers()
    if not tickers:
        print("Не удалось получить данные с Bybit. Пропускаем итерацию.")
        return

    old_data = load_old_data()
    new_state = {}

    # Берем ТОП-20 для максимальной надежности и скорости в GitHub Actions
    top_symbols = sorted(tickers.keys(), key=lambda x: float(tickers[x]['volume24h']), reverse=True)[:20]

    for symbol in top_symbols:
        try:
            price = float(tickers[symbol]['lastPrice'])
            oi = get_oi_for_symbol(symbol)
            if oi == 0: continue
            
            new_state[symbol] = {"oi": oi, "price": price}

            if symbol in old_data:
                old_oi = old_data[symbol].get('oi', 0)
                old_price = old_data[symbol].get('price', 0)
                
                if old_oi > 0:
                    change = ((oi - old_oi) / old_oi) * 100
                    if change >= OI_THRESHOLD:
                        emoji = "📈" if price >= old_price else "📉"
                        side = "LONG" if price >= old_price else "SHORT"
                        msg = f"{emoji} **BYBIT ALERT: {symbol}**\nOI: +{change:.2f}%\nSide: {side}\nPrice: {price}"
                        bot.send_message(CHAT_ID, msg)
        except Exception as e:
            print(f"Ошибка обработки {symbol}: {e}")

    with open(DATA_FILE, 'w') as f:
        json.dump(new_state, f, indent=4)
    print("Готово!")

if __name__ == "__main__":
    main()
