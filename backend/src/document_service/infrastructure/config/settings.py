from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "Document Management Service"
    api_prefix: str = "/api/v1"
    max_docx_size_bytes: int = Field(default=50 * 1024 * 1024, gt=0)

    database_url: str = "postgresql+asyncpg://document_service:document_service@localhost:5432/document_service"
    broker_url: str = "amqp://guest:guest@localhost:5672//"

    s3_endpoint_url: str = "https://s3.twcstorage.ru"
    s3_bucket: str = ""
    s3_region: str = "ru-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    openai_api_key: str = ""
    astra_model: str = "gpt-6-astra"
    yandex_gpt_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_model_uri: str = ""
    prompt_root: str = "prompts/docx-to-html"
    prompt_package_version: str = "v2"
    document_theme_id: str = "villartec-manual-a4"
    document_theme_version: str = "1.0"
    docx_converter_url: str = "http://gotenberg:3000"
    docx_converter_timeout_seconds: float = Field(default=180.0, gt=0)
    style_reference_pdf_path: str = "reference/style-reference.pdf"
    style_reference_overview_dir: str = "reference/overview"
    max_ai_file_input_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    renderer_url: str = "http://renderer:3000"
    publication_base_url: str = ""

    auth_issuer: str = ""
    auth_audience: str = ""
    auth_jwks_url: str = ""
    basic_auth_username: str = ""
    basic_auth_password: str = ""
    basic_auth_user_id: str = "00000000-0000-0000-0000-000000000001"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env != "production":
            return self
        required = {
            "S3_BUCKET": self.s3_bucket,
            "S3_ACCESS_KEY": self.s3_access_key,
            "S3_SECRET_KEY": self.s3_secret_key,
            "OPENAI_API_KEY": self.openai_api_key,
            "YANDEX_GPT_API_KEY": self.yandex_gpt_api_key,
            "YANDEX_FOLDER_ID": self.yandex_folder_id,
            "YANDEX_MODEL_URI": self.yandex_model_uri,
            "AUTH_ISSUER": self.auth_issuer,
            "AUTH_AUDIENCE": self.auth_audience,
            "AUTH_JWKS_URL": self.auth_jwks_url,
            "BASIC_AUTH_USERNAME": self.basic_auth_username,
            "BASIC_AUTH_PASSWORD": self.basic_auth_password,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing production settings: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
