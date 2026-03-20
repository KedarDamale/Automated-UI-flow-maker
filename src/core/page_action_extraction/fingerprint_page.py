# Page state fingerprinting — produces a stable hash that changes when the
# user would perceive a meaningful state transition, even in SPAs where the
# URL might stay the same.
from config.Crawler import NOISE_PARAMS,FINGERPRINT_JS
from config.logger import logger
from urllib.parse import urlparse, parse_qs, urlencode
import json
import hashlib
from playwright.async_api import Page

async def fingerprint_page(page:Page)->str:
    #returns hash representing the current UI state

    try:
        signals: dict = await page.evaluate(FINGERPRINT_JS)
        logger.log(f"Signals detected: \n{signals}","info")
    except Exception:
        signals = {"url": page.url, "title": await page.title()}
        logger.log(f"Signals not detected, using fallback:\n{signals}","info")
    
    url = signals.get("url", "")#stripping off params and Qparams
    logger.log(f"URL: {url}","info")
    parsed = urlparse(url)
    logger.log(f"Parsed URL: {parsed}","info")
    qs = parse_qs(parsed.query)
    logger.log(f"Query String: {qs}","info")
    clean_qs = {k: v for k, v in qs.items() if k not in NOISE_PARAMS}
    logger.log(f"Clean Query String: {clean_qs}","info")
    clean_url = parsed._replace(query=urlencode(clean_qs, doseq=True)).geturl()
    logger.log(f"Clean URL: {clean_url}","info")
    signals["url"] = clean_url
    logger.log(f"Altered Signals: {signals}","info")

    blob = json.dumps(signals, sort_keys=True)
    logger.log(f"Blob: {blob}","info")

    hash_val = hashlib.sha256(blob.encode()).hexdigest()
    logger.log(f"Hash Value: {hash_val}","info")
    return hash_val