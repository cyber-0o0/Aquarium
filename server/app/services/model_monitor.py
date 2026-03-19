import asyncio
import time
from datetime import datetime, UTC
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.core.models_registry import SUPPORTED_MODELS
from app.models.model_status import ModelStatus
from app.services.agent_runtime import _build_llm, _resolve_api_key
from langchain_core.messages import HumanMessage

# Интервал проверки (3.5 часа)
CHECK_INTERVAL = 3.5 * 60 * 60 

async def monitor_models_task():
    """Фоновая задача для мониторинга доступности ИИ-моделей."""
    print("Model monitoring task initialized.")
    
    # Даем приложению немного времени на запуск перед первой проверкой
    await asyncio.sleep(10)
    
    while True:
        try:
            print(f"[{datetime.now(UTC)}] Periodic model check started.")
            async with AsyncSessionLocal() as db:
                for model_id, config in SUPPORTED_MODELS.items():
                    # For platform monitoring, we use a dummy user_id or handle it in _resolve_api_key
                    # In this platform task, we only care about keys from .env (platform keys)
                    # _resolve_api_key(user_id, model_id, db)
                    from app.services.agent_runtime import _resolve_api_key
                    api_key, base_url = await _resolve_api_key(None, model_id, db)

                    if not api_key:
                        # Если ключа нет в .env, пропускаем мониторинг платформой
                        continue
                    
                    status = "active"
                    error_msg = None
                    latency = 0
                    
                    try:
                        llm = _build_llm(
                            model_id=model_id,
                            max_tokens=5, 
                            temperature=0.0,
                            api_key=api_key,
                            base_url=base_url
                        )
                        start = time.perf_counter()
                        # Маленький запрос для проверки жизни
                        await llm.ainvoke([HumanMessage(content="ping")])
                        latency = time.perf_counter() - start
                        
                        if latency > 15.0: # Порог для "нестабильности"
                             status = "unstable"
                             
                    except Exception as e:
                        status = "offline"
                        error_msg = str(e)
                        print(f"[{model_id}] CHECK FAILED: {status} - {error_msg}")
                    
                    # Обновляем БД
                    res = await db.execute(select(ModelStatus).where(ModelStatus.id == model_id))
                    obj = res.scalar_one_or_none()
                    
                    if not obj:
                        obj = ModelStatus(
                            id=model_id,
                            provider=config["provider"],
                            status=status,
                            latency=latency,
                            error=error_msg,
                            last_checked=datetime.now(UTC)
                        )
                        db.add(obj)
                    else:
                        obj.status = status
                        obj.latency = latency
                        obj.error = error_msg
                        obj.last_checked = datetime.now(UTC)
                    
                    await db.commit()
            print(f"[{datetime.now(UTC)}] Periodic model check finished.")
        except Exception as e:
            print(f"Error in model monitoring task: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)
