from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    bot_token: SecretStr
    admin_id: int
    
    # Analytics Dashboard settings
    analytics_api_url: str = "http://localhost:8000"
    analytics_api_key: str = "changeme"
    payment_token: SecretStr = SecretStr("")
    
    # SMTP Settings
    smtp_host: str = "smtp.yandex.ru"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: SecretStr = SecretStr("")
    smtp_from: str = ""
    
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

config = Settings()
