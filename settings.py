# pyright: reportIncompatibleVariableOverride=false
import pydantic_settings


class Settings(pydantic_settings.BaseSettings):
    model_config: pydantic_settings.SettingsConfigDict = (
        pydantic_settings.SettingsConfigDict(env_prefix="QTHREADER_")
    )

    database_url: str = "sqlite:///items.db"


settings = Settings()
