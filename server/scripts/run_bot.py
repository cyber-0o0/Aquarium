import asyncio
import sys
import os

# Добавляем корневую директорию сервера в пути импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.telegram_bot import start_polling
from app.core.config import settings

async def main():
    print("🤖 Запуск Telegram Bot в режиме Long Polling...")
    print(f"Token: {settings.TELEGRAM_BOT_TOKEN[:10]}... (проверка настроек)")
    
    # Объект статистики для вывода в консоль
    stats = {"loops": 0, "total_updates": 0, "is_running": True}
    
    try:
        await start_polling(stats)
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
