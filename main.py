import requests
import time
import telebot

# --- НАСТРОЙКИ ---
import os
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OI_THRESHOLD = 5.0      # Сигнал, если OI вырос на 5% за 5 минут
CHECK_INTERVAL = 300    # Проверка каждые 5 минут (300 сек)

bot = telebot.TeleBot(TG_TOKEN)

def get_bybit_market_data():
    """Получает цены и список всех монет на фьючерсах Bybit"""
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    try:
        response = requests.get(url).json()
        if response['retCode'] == 0:
            # Создаем словарь {Символ: Цена}
            return {item['symbol']: float(item['lastPrice']) for item in response['result']['list'] if 'USDT' in item['symbol']}
    except Exception as e:
        print(f"Ошибка получения цен: {e}")
    return {}

def get_symbol_oi(symbol):
    """Получает текущий открытый интерес для конкретной монеты"""
    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min"
    try:
        response = requests.get(url).json()
        if response['retCode'] == 0 and len(response['result']['list']) > 0:
            return float(response['result']['list'][0]['openInterest'])
    except Exception as e:
        pass
    return 0

def monitor():
    last_oi_data = {} # Хранилище для сравнения
    print("Бот Bybit запущен. Сканирую рынок...")
    
    while True:
        current_prices = get_bybit_market_data()
        symbols = list(current_prices.keys())
        
        # Сканируем топ-100 самых активных монет для экономии лимитов API
        for symbol in symbols[:100]:
            current_oi = get_symbol_oi(symbol)
            
            if symbol in last_oi_data:
                old_oi = last_oi_data[symbol]
                oi_change = ((current_oi - old_oi) / old_oi) * 100 if old_oi > 0 else 0
                
                # Если OI вырос выше порога
                if oi_change >= OI_THRESHOLD:
                    price = current_prices[symbol]
                    msg = (f"🔥 **BYBIT WHALE ALERT: {symbol}**\n\n"
                           f"📊 Рост OI: `+{oi_change:.2f}%` за 5 мин\n"
                           f"💰 Цена: `{price}`\n"
                           f"🔗 [Открыть на Bybit](https://www.bybit.com/trade/usdt/{symbol})")
                    
                    bot.send_message(CHAT_ID, msg, parse_mode="Markdown", disable_web_page_preview=True)
                    print(f"Сигнал по {symbol}: +{oi_change:.2f}% OI")
            
            last_oi_data[symbol] = current_oi
            time.sleep(0.2) # Небольшая пауза, чтобы Bybit не забанил за частые запросы
            
        print(f"Цикл проверки завершен. Спим {CHECK_INTERVAL} сек...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        monitor()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        time.sleep(60)
