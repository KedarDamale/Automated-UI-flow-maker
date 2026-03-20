from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str
    AZURE_DEPLOYMENT_NAME: str

    CRAWL_URL: str
    MAX_DEPTH: int=99999
    MAX_NODES: int=99999


settings=Settings()
