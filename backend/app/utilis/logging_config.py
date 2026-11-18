import logging

from app.utilis.config import settings

def setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for noisy in ("httpx", "httpcore","httpx2","huggingface_hub","sentence_transformers","google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)