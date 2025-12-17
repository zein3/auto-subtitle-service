from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_path: str = "models/ggml-large-v3.bin"

    model_config = SettingsConfigDict(env_file = '.env')

settings = Settings()