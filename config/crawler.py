from pydantic import BaseModel
from .settings import settings

class CrawlerConfig(BaseModel):
    #crawl config
    CRAWL_URL: str = settings.CRAWL_URL
    MAX_DEPTH: int = settings.MAX_DEPTH
    MAX_NODES: int = settings.MAX_NODES
    STAY_ON_ORIGIN: bool = True

    #browser config
    BROWSER_HEADLESS:bool=True
    BROWSER_VIEWPORT:dict | None = field(default_factory=lambda: {"width": 1280, "height": 800})
    BROWSER_EXTRA_HEADERS:dict = field(default_factory=dict)

    #cookie config
    COOKIES:list[dict] = field(default_factory=list)

    #login details
    LOGIN_URL:str
    LOGIN_STEPS: list[dict] = field(default_factory=list)
    LOGIN_USERNAME:str
    LOGIN_PASSWORD:str


    
