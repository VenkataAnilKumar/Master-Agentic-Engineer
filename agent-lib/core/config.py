"""Configuration management for agent systems.

This module provides comprehensive configuration management with validation,
environment variable support, and production-ready defaults for agent systems.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from enum import Enum

from pydantic import BaseModel, Field, validator, root_validator


class LogLevel(str, Enum):
    """Logging level enumeration."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DeploymentEnvironment(str, Enum):
    """Deployment environment enumeration."""
    
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    url: str = Field(..., description="Database connection URL")
    pool_size: int = Field(default=10, ge=1, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, description="Maximum pool overflow")
    pool_timeout: int = Field(default=30, ge=1, description="Pool timeout in seconds")
    echo: bool = Field(default=False, description="Enable SQL query logging")
    
    @validator("url")
    def validate_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "sqlite://", "mysql://", "redis://")):
            raise ValueError("Invalid database URL scheme")
        return v


class RedisConfig(BaseModel):
    """Redis configuration for caching and message queuing."""
    
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    password: Optional[str] = Field(default=None, description="Redis password")
    db: int = Field(default=0, ge=0, description="Redis database number")
    ssl: bool = Field(default=False, description="Enable SSL/TLS")
    socket_timeout: int = Field(default=30, gt=0, description="Socket timeout in seconds")
    connection_pool_max_connections: int = Field(default=50, gt=0, description="Max connections in pool")
    
    @property
    def url(self) -> str:
        """Generate Redis URL from configuration."""
        scheme = "rediss" if self.ssl else "redis"
        auth = f":{self.password}@" if self.password else ""
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"


class SecurityConfig(BaseModel):
    """Security configuration."""
    
    secret_key: str = Field(..., description="Secret key for encryption and signing")
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(default=30, gt=0, description="Access token expiration")
    refresh_token_expire_days: int = Field(default=7, gt=0, description="Refresh token expiration")
    password_min_length: int = Field(default=8, ge=4, description="Minimum password length")
    max_login_attempts: int = Field(default=5, ge=1, description="Maximum login attempts")
    lockout_duration_minutes: int = Field(default=15, ge=1, description="Account lockout duration")
    
    # CORS settings
    cors_origins: List[str] = Field(default_factory=list, description="Allowed CORS origins")
    cors_allow_credentials: bool = Field(default=True, description="Allow CORS credentials")
    
    # Rate limiting
    rate_limit_requests: int = Field(default=100, gt=0, description="Rate limit requests per window")
    rate_limit_window_minutes: int = Field(default=1, gt=0, description="Rate limit window in minutes")
    
    @validator("secret_key")
    def validate_secret_key(cls, v):
        """Validate secret key strength."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v


class ObservabilityConfig(BaseModel):
    """Observability and monitoring configuration."""
    
    # Logging
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Global log level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    # Metrics
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9090, ge=1024, le=65535, description="Metrics server port")
    metrics_path: str = Field(default="/metrics", description="Metrics endpoint path")
    
    # Tracing
    enable_tracing: bool = Field(default=True, description="Enable distributed tracing")
    jaeger_endpoint: Optional[str] = Field(default=None, description="Jaeger collector endpoint")
    sampling_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Trace sampling rate")
    
    # Health checks
    health_check_interval: int = Field(default=30, gt=0, description="Health check interval in seconds")
    health_check_timeout: int = Field(default=10, gt=0, description="Health check timeout in seconds")


class AgentSystemConfig(BaseModel):
    """Agent system configuration."""
    
    # Agent defaults
    default_model: str = Field(default="gpt-4", description="Default LLM model")
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Default temperature")
    default_max_tokens: int = Field(default=4096, gt=0, description="Default max tokens")
    default_timeout: int = Field(default=300, gt=0, description="Default task timeout in seconds")
    
    # Execution limits
    max_concurrent_agents: int = Field(default=10, ge=1, description="Maximum concurrent agents")
    max_tasks_per_agent: int = Field(default=5, ge=1, description="Maximum tasks per agent")
    task_queue_size: int = Field(default=1000, ge=1, description="Task queue size")
    
    # Memory settings
    memory_backend: str = Field(default="chromadb", description="Memory backend type")
    memory_collection_name: str = Field(default="agent_memory", description="Memory collection name")
    memory_persist_directory: Optional[str] = Field(default=None, description="Memory persistence directory")
    
    # Tool settings
    tool_timeout: int = Field(default=60, gt=0, description="Default tool timeout in seconds")
    max_tool_retries: int = Field(default=2, ge=0, description="Maximum tool retry attempts")
    
    @validator("memory_backend")
    def validate_memory_backend(cls, v):
        """Validate memory backend options."""
        valid_backends = ["chromadb", "pinecone", "weaviate", "redis", "memory"]
        if v not in valid_backends:
            raise ValueError(f"Invalid memory backend: {v}. Valid options: {valid_backends}")
        return v


class APIConfig(BaseModel):
    """API server configuration."""
    
    host: str = Field(default="0.0.0.0", description="API server host")
    port: int = Field(default=8000, ge=1024, le=65535, description="API server port")
    workers: int = Field(default=1, ge=1, description="Number of worker processes")
    reload: bool = Field(default=False, description="Enable auto-reload in development")
    
    # Request limits
    max_request_size: int = Field(default=16777216, gt=0, description="Max request size in bytes")  # 16MB
    timeout_keep_alive: int = Field(default=5, gt=0, description="Keep-alive timeout in seconds")
    
    # API versioning
    api_version: str = Field(default="v1", description="API version")
    api_prefix: str = Field(default="/api", description="API path prefix")
    
    # Documentation
    docs_url: Optional[str] = Field(default="/docs", description="OpenAPI docs URL")
    redoc_url: Optional[str] = Field(default="/redoc", description="ReDoc URL")
    openapi_url: Optional[str] = Field(default="/openapi.json", description="OpenAPI spec URL")


class SystemConfig(BaseModel):
    """Main system configuration."""
    
    # Environment
    environment: DeploymentEnvironment = Field(default=DeploymentEnvironment.DEVELOPMENT)
    debug: bool = Field(default=False, description="Enable debug mode")
    testing: bool = Field(default=False, description="Enable testing mode")
    
    # Service configuration
    api: APIConfig = Field(default_factory=APIConfig)
    database: Optional[DatabaseConfig] = Field(default=None)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    security: SecurityConfig = Field(...)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    agents: AgentSystemConfig = Field(default_factory=AgentSystemConfig)
    
    # External services
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    google_api_key: Optional[str] = Field(default=None, description="Google API key")
    
    # File paths
    data_directory: str = Field(default="./data", description="Data storage directory")
    logs_directory: str = Field(default="./logs", description="Logs storage directory")
    cache_directory: str = Field(default="./cache", description="Cache storage directory")
    
    @root_validator
    def validate_production_settings(cls, values):
        """Validate production-specific settings."""
        env = values.get("environment")
        debug = values.get("debug")
        
        if env == DeploymentEnvironment.PRODUCTION:
            if debug:
                raise ValueError("Debug mode must be disabled in production")
            
            security = values.get("security")
            if security and len(security.secret_key) < 64:
                raise ValueError("Production secret key must be at least 64 characters")
        
        return values
    
    @validator("data_directory", "logs_directory", "cache_directory")
    def create_directories(cls, v):
        """Create directories if they don't exist."""
        Path(v).mkdir(parents=True, exist_ok=True)
        return v
    
    class Config:
        """Pydantic configuration."""
        env_prefix = "AGENT_"
        env_nested_delimiter = "__"
        case_sensitive = False


def load_config(config_path: Optional[Union[str, Path]] = None) -> SystemConfig:
    """Load configuration from file and environment variables.
    
    Args:
        config_path: Path to configuration file (YAML or JSON)
        
    Returns:
        SystemConfig instance with loaded configuration
        
    Raises:
        FileNotFoundError: If config file is specified but not found
        ValueError: If configuration is invalid
    """
    config_data = {}
    
    # Load from file if specified
    if config_path:
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "r") as f:
            if config_path.suffix.lower() in [".yaml", ".yml"]:
                config_data = yaml.safe_load(f) or {}
            elif config_path.suffix.lower() == ".json":
                config_data = json.load(f) or {}
            else:
                raise ValueError(f"Unsupported config file format: {config_path.suffix}")
    
    # Load default configuration paths
    default_paths = [
        Path("config.yaml"),
        Path("config.yml"),
        Path("config.json"),
        Path("config") / "config.yaml",
        Path("config") / "config.yml",
        Path("config") / "config.json"
    ]
    
    for default_path in default_paths:
        if not config_path and default_path.exists():
            with open(default_path, "r") as f:
                if default_path.suffix.lower() in [".yaml", ".yml"]:
                    config_data = yaml.safe_load(f) or {}
                elif default_path.suffix.lower() == ".json":
                    config_data = json.load(f) or {}
            break
    
    # Ensure required security configuration
    if "security" not in config_data:
        secret_key = os.getenv("AGENT_SECRET_KEY")
        if not secret_key:
            # Generate a random secret key for development
            import secrets
            secret_key = secrets.token_urlsafe(64)
            if config_data.get("environment") == "production":
                raise ValueError("SECRET_KEY must be set in production environment")
        
        config_data["security"] = {"secret_key": secret_key}
    
    # Create configuration instance (Pydantic will handle env vars)
    try:
        return SystemConfig(**config_data)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}")


def validate_config(config: SystemConfig) -> List[str]:
    """Validate configuration and return list of warnings/issues.
    
    Args:
        config: Configuration to validate
        
    Returns:
        List of validation warnings
    """
    warnings = []
    
    # Check for missing API keys in production
    if config.environment == DeploymentEnvironment.PRODUCTION:
        if not config.openai_api_key and not config.anthropic_api_key:
            warnings.append("No LLM API keys configured for production")
        
        if config.debug:
            warnings.append("Debug mode is enabled in production")
        
        if config.api.reload:
            warnings.append("Auto-reload is enabled in production")
    
    # Check security settings
    if config.security.cors_origins == ["*"]:
        warnings.append("CORS is configured to allow all origins")
    
    if config.observability.sampling_rate == 1.0:
        warnings.append("Tracing sampling rate is 100% - may impact performance")
    
    # Check resource limits
    if config.agents.max_concurrent_agents > 50:
        warnings.append("High concurrent agent limit may impact performance")
    
    return warnings


def get_config_summary(config: SystemConfig) -> Dict[str, Any]:
    """Get a summary of the current configuration.
    
    Args:
        config: Configuration to summarize
        
    Returns:
        Dictionary containing configuration summary
    """
    return {
        "environment": config.environment,
        "debug": config.debug,
        "api": {
            "host": config.api.host,
            "port": config.api.port,
            "workers": config.api.workers
        },
        "database_configured": config.database is not None,
        "redis": {
            "host": config.redis.host,
            "port": config.redis.port,
            "ssl": config.redis.ssl
        },
        "security": {
            "algorithm": config.security.algorithm,
            "cors_enabled": bool(config.security.cors_origins),
            "rate_limiting": {
                "requests": config.security.rate_limit_requests,
                "window_minutes": config.security.rate_limit_window_minutes
            }
        },
        "observability": {
            "log_level": config.observability.log_level,
            "metrics_enabled": config.observability.enable_metrics,
            "tracing_enabled": config.observability.enable_tracing
        },
        "agents": {
            "default_model": config.agents.default_model,
            "max_concurrent": config.agents.max_concurrent_agents,
            "memory_backend": config.agents.memory_backend
        },
        "api_keys_configured": {
            "openai": bool(config.openai_api_key),
            "anthropic": bool(config.anthropic_api_key),
            "google": bool(config.google_api_key)
        }
    }


# Configuration validation decorator
def require_config(config_attr: str):
    """Decorator to ensure configuration attribute is set.
    
    Args:
        config_attr: Configuration attribute path (e.g., "database.url")
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be implemented to check configuration
            # For now, just pass through
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Example configuration file templates
DEVELOPMENT_CONFIG_TEMPLATE = """
environment: development
debug: true

api:
  host: "127.0.0.1"
  port: 8000
  reload: true

redis:
  host: "localhost"
  port: 6379

security:
  secret_key: "development-secret-key-change-in-production"
  cors_origins: ["http://localhost:3000"]

observability:
  log_level: "DEBUG"
  enable_metrics: true
  enable_tracing: false

agents:
  default_model: "gpt-3.5-turbo"
  max_concurrent_agents: 5
  memory_backend: "memory"
"""

PRODUCTION_CONFIG_TEMPLATE = """
environment: production
debug: false

api:
  host: "0.0.0.0"
  port: 8000
  workers: 4

database:
  url: "${DATABASE_URL}"
  pool_size: 20
  max_overflow: 30

redis:
  host: "${REDIS_HOST}"
  port: ${REDIS_PORT}
  password: "${REDIS_PASSWORD}"
  ssl: true

security:
  secret_key: "${SECRET_KEY}"
  cors_origins: ["https://yourdomain.com"]
  rate_limit_requests: 1000
  rate_limit_window_minutes: 1

observability:
  log_level: "INFO"
  log_format: "json"
  enable_metrics: true
  enable_tracing: true
  jaeger_endpoint: "${JAEGER_ENDPOINT}"
  sampling_rate: 0.1

agents:
  default_model: "gpt-4"
  max_concurrent_agents: 20
  memory_backend: "chromadb"
  memory_persist_directory: "/app/data/memory"

openai_api_key: "${OPENAI_API_KEY}"
anthropic_api_key: "${ANTHROPIC_API_KEY}"
"""