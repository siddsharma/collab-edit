from pydantic_settings import BaseSettings
from pydantic import Field, validator
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Database
    database_url: str = Field(
        default="postgresql://noteuser:notepass@localhost:5432/collaborative_notes",
        description="PostgreSQL database URL"
    )
    
    # Firebase
    firebase_project_id: str = Field(default="", description="Firebase project ID")
    firebase_private_key_id: str = Field(default="", description="Firebase private key ID")
    firebase_private_key: str = Field(default="", description="Firebase private key")
    firebase_client_email: str = Field(default="", description="Firebase client email")
    firebase_client_id: str = Field(default="", description="Firebase client ID")
    firebase_auth_uri: str = Field(
        default="https://accounts.google.com/o/oauth2/auth",
        description="Firebase auth URI"
    )
    firebase_token_uri: str = Field(
        default="https://oauth2.googleapis.com/token",
        description="Firebase token URI"
    )
    
    # CORS
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost",
        description="Comma-separated list of allowed origins"
    )
    
    # Environment
    environment: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator('environment')
    def validate_environment(cls, v):
        valid_environments = ['development', 'staging', 'production']
        if v not in valid_environments:
            raise ValueError(f'Environment must be one of {valid_environments}')
        return v

    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of {valid_levels}')
        return v.upper()

    def get_cors_origins(self) -> list:
        """Get CORS origins list"""
        if isinstance(self.allowed_origins, str):
            return [origin.strip() for origin in self.allowed_origins.split(',')]
        return self.allowed_origins

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == 'production'

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == 'development'


# Global settings instance
try:
    settings = Settings()
    logger.info(f"Settings loaded successfully for environment: {settings.environment}")
except Exception as e:
    logger.error(f"Failed to load settings: {e}")
    raise
