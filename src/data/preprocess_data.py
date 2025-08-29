import re, langid
from typing import List
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

MODEL_NAME = "facebook/m2m100_418M"
tokenizer = M2M100Tokenizer.from_pretrained(MODEL_NAME)
model = M2M100ForConditionalGeneration.from_pretrained(MODEL_NAME)

LANG_CODE_MAP = {
    "en": "en",  # English
    "fr": "fr",  # French
    "es": "es",  # Spanish
    "de": "de",  # German
    "zh": "zh",  # Chinese
    "ja": "ja",  # Japanese
    "ko": "ko",  # Korean
    "id": "id",  # Indonesian
    "ms": "ms",  # Malay
}

def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"http\S+|www\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def detect_lang(text: str) -> str:
    lang, _ = langid.classify(text)
    return lang

def translate_to_english(text: str, src_lang: str) -> str:
    if src_lang == "en":
        return text  # no translation needed
    
    src_lang_m2m = LANG_CODE_MAP.get(src_lang, None)
    if not src_lang_m2m:
        return text
    
    tokenizer.src_lang = src_lang_m2m
    encoded = tokenizer(text, return_tensors="pt")
    generated_tokens = model.generate(
        **encoded, 
        forced_bos_token_id=tokenizer.get_lang_id("en")
    )
    return tokenizer.decode(generated_tokens[0], skip_special_tokens=True)