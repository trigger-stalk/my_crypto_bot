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

def get_bybit_tickers():
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    try:
        res = requests.get(url, timeout=15).json()
        if res.get('retCode') == 0:
            return {item['symbol']: item for item in res['result']['list'] if 'USDT' in item['symbol']}
    except Exception as e:
        print(f"Bybit API Error: {e}")
    return {}

def get_oi_for_symbol(symbol):
    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min"
    try:
        time.sleep(0.2) # Чтобы Bybit не ругался на частоту запросов
        res = requests.get(url, timeout=15).json()
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

    tickers = get_bybit_tickers()
    if not tickers: return
    
    old_data = load_old_data()
    new_state = {}

    # Берем ТОП-25 монет по объему (самые активные)
    top_symbols = sorted(tickers.keys(), key=lambda x: float(tickers[x]['volume24h']), reverse=True)[:25]

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
                           f"🔥 Рост OI: `+{change:.2f}%`\n"
                           f"🎯 Направление: **{side}**\n"
                           f"💰 Цена: `{price}`\n"
                           f"🔗 [Bybit](https://www.bybit.com/trade/usdt/{symbol})")
                    try:
                        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                    except:
                        pass

    with open(DATA_FILE, 'w') as f:
        json.dump(new_state, f, indent=4)

if __name__ == "__main__":
    main()
