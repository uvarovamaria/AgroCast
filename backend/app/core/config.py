# app/core/config.py

class Settings:
    def __init__(self) -> None:
        # Название приложения
        self.app_name: str = "AgroCast API"
        # Префикс для всех v1-роутов
        self.api_v1_prefix: str = "/api/v1"


# Глобальный объект настроек, который импортируется в main.py
settings = Settings()
