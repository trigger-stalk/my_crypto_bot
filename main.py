import os
import requests
import json
import telebot
import time

# Данные из Secrets GitHub
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OI_THRESHOLD = 5.0  # Порог срабатывания %
DATA_FILE = "market_state.json"

bot = telebot.TeleBot(TG_TOKEN)

# Заголовки, чтобы Bybit думал, что заходит человек через браузер
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

def get_bybit_tickers():
    # Используем зеркало bytick.com, оно лучше работает в GitHub Actions
    url = "https://api.bytick.com/v5/market/tickers?category=linear"
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            print(f"Ошибка API: Статус {response.status_code}")
            return {}
        
        res = response.json()
        if res.get('retCode') == 0:
            return {item['symbol']: item for item in res['result']['list'] if 'USDT' in item['symbol']}
    except Exception as e:
        print(f"Критическая ошибка Bybit API: {e}")
    return {}

def get_oi_for_symbol(symbol):
    url = f"https://api.bytick.com/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min"
    try:
        time.sleep(0.5) # Пауза 0.5 сек между монетами, чтобы не забанили
        res = requests.get(url, headers=HEADERS, timeout=15).json()
        if res.get('retCode') == 0 and res.get('result') and len(res['result']['list']) > 0:
            return float(res['result']['list'][0]['openInterest'])
    except:
        return 0
    return 0

def load_old_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except:
            return {}
    return {}

def main():
    if not TG_TOKEN or not CHAT_ID:
        print("Ошибка: Проверьте Secrets (TG_TOKEN и CHAT_ID)")
        return

    print("Запрашиваю тикеры...")
    tickers = get_bybit_tickers()
    if not tickers: 
        print("Данные не получены. Завершаю.")
        return
    
    old_data = load_old_data()
    new_state = {}

    # Берем ТОП-20 монет по объему (самые ликвидные)
    top_symbols = sorted(tickers.keys(), key=lambda x: float(tickers[x]['volume24h']), reverse=True)[:20]
    print(f"Обрабатываю монеты: {', '.join(top_symbols)}")

    for symbol in top_symbols:
        price = float(tickers[symbol]['lastPrice'])
        oi = get_oi_for_symbol(symbol)
        
        if oi == 0: continue
        new_state[symbol] = {"oi": oi, "price": price}

        if symbol in old_data:
            o_oi = old_data[symbol].get('oi', 0)
            o_pr = old_data[symbol].get('price', 0)
            
            if o_oi > 0:
                change = ((oi - o_oi) / o_oi) * 100
                if change >= OI_THRESHOLD:
                    emoji = "📈" if price >= o_pr else "📉"
                    side = "LONG" if price >= o_pr else "SHORT"
                    msg = (f"{emoji} **BYBIT ALERT: {symbol}**\n"
                           f"🔥 Рост OI: `+{change:.2f}%` (5м)\n"
                           f"🎯 Направление: **{side}**\n"
                           f"💰 Цена: `{price}`\n"
                           f"🔗 [Bybit](https://www.bybit.com/trade/usdt/{symbol})")
                    try:
                        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                        print(f"Сигнал отправлен: {symbol}")
                    except:
                        pass

    with open(DATA_FILE, 'w') as f:
        json.dump(new_state, f, indent=4)
    print("Данные успешно сохранены в файл.")

if __name__ == "__main__":
    main()
