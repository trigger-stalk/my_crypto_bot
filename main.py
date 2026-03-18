import os
import requests
import json
import telebot

# --- НАСТРОЙКИ (Берем из секретов GitHub) ---
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OI_THRESHOLD = 5.0  # Порог в 5%
DATA_FILE = "market_state.json"

bot = telebot.TeleBot(TG_TOKEN)

def get_bybit_data():
    """Получает данные по топ-100 монетам (OI и Цена) за один запрос"""
    # Используем эндпоинт тикеров, где для некоторых категорий есть данные OI
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    try:
        response = requests.get(url).json()
        if response['retCode'] == 0:
            # Берем первые 100 монет по объему (или просто список)
            data = {}
            for item in response['result']['list']:
                if 'USDT' in item['symbol']:
                    symbol = item['symbol']
                    # В тикерах не всегда есть точный OI, берем его через доп. поле или отдельный запрос
                    # Для надежности в Actions лучше делать точечно для ТОП-50
                    data[symbol] = {
                        "price": float(item['lastPrice']),
                        "volume": float(item['volume24h'])
                    }
            return data
    except:
        return {}

def get_oi_for_symbol(symbol):
    """Получаем свежий OI для конкретного символа"""
    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min"
    try:
        res = requests.get(url).json()
        if res['retCode'] == 0 and len(res['result']['list']) > 0:
            return float(res['result']['list'][0]['openInterest'])
    except:
        return 0

def load_old_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_current_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def main():
    print("Запуск сканирования Bybit...")
    current_market = get_bybit_data()
    old_data = load_old_data()
    new_state = {}

    # Сканируем топ-30 самых волатильных монет (чтобы вписаться в лимиты GitHub)
    top_symbols = sorted(current_market.keys(), key=lambda x: current_market[x]['volume'], reverse=True)[:30]

    for symbol in top_symbols:
        current_oi = get_oi_for_symbol(symbol)
        current_price = current_market[symbol]['price']
        new_state[symbol] = {"oi": current_oi, "price": current_price}

        if symbol in old_data:
            old_oi = old_data[symbol]['oi']
            old_price = old_data[symbol]['price']
            
            if old_oi > 0:
                oi_change = ((current_oi - old_oi) / old_oi) * 100
                
                if oi_change >= OI_THRESHOLD:
                    direction = "📈 LONG-Bias" if current_price > old_price else "📉 SHORT-Bias"
                    msg = (f"🔔 **BYBIT ANOMALY**\n\n"
                           f"🪙 Монета: #{symbol}\n"
                           f"📊 Рост OI: `+{oi_change:.2f}%`\n"
                           f"⚡️ Направление: {direction}\n"
                           f"💰 Цена: `{current_price}`\n"
                           f"🔗 [Торговать](https://www.bybit.com/trade/usdt/{symbol})")
                    bot.send_message(CHAT_ID, msg, parse_mode="Markdown")

    save_current_data(new_state)
    print("Проверка завершена, данные сохранены.")

if __name__ == "__main__":
    main()
