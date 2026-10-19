# Deterministic slot extraction for the structured values this assistant cares
# about: order IDs, dates, discount codes, product names, and email addresses.

import re

import dateparser.search

from . import config

# Every regex below is built from config.py's knobs rather than hardcoded,
# so tuning the accepted shapes (ID prefix, code length, cue words, ...)
# never requires touching this file. See config.py for what each knob means.

_ORDER_ID_RE = re.compile(rf"\b{re.escape(config.ORDER_ID_PREFIX)}\d+\b", re.IGNORECASE)
_BARE_NUMBER_RE = re.compile(rf"\b\d{{{config.BARE_NUMBER_MIN_DIGITS},}}\b")

# Promo codes are conventionally all-caps and mix letters with digits
# (SAVE20, WELCOME15) -- matched directly, no context needed. A pure-letters
# code like FREESHIP is indistinguishable from any other capitalized word on
# its own, so it's only accepted as a fallback when one of
# config.DISCOUNT_CONTEXT_KEYWORDS appears somewhere in the same turn. A
# code-shaped word without context is rejected as ambiguous.
_code_len = rf"{config.DISCOUNT_CODE_MIN_LEN},{config.DISCOUNT_CODE_MAX_LEN}"
_DISCOUNT_CODE_RE = re.compile(rf"\b(?=[A-Z0-9]{{{_code_len}}}\b)[A-Z]+[0-9]+[A-Z0-9]*\b")
_DISCOUNT_CODE_LETTERS_RE = re.compile(rf"\b[A-Z]{{{_code_len}}}\b")
_DISCOUNT_CONTEXT_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in config.DISCOUNT_CONTEXT_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Product names in this MVP are assumed Title Case in the transcript (as a
# real UI/catalog would render them, e.g. "the Aurora Desk Lamp") -- the
# regex captures the run of capitalized words after a determiner
# (config.PRODUCT_NAME_CUE_WORDS) and stops at the first word that isn't
# Title Case. Free-form product references without those cues or consistent
# capitalization are intentionally not guessed.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_cue_alternation = "|".join(re.escape(w) for w in config.PRODUCT_NAME_CUE_WORDS)
_word_min_extra_chars = max(config.PRODUCT_NAME_MIN_WORD_LEN - 1, 0)  # 1st char is [A-Z]
_PRODUCT_NAME_RE = re.compile(
    rf"\b(?:(?i:{_cue_alternation}))\s+"
    rf"((?:[A-Z][A-Za-z0-9'\-]{{{_word_min_extra_chars},}}\s*){{1,{config.PRODUCT_NAME_MAX_WORDS}}})"
)


def extract_order_id(text):
    """ORD-NNNN if present, otherwise a bare order/account-style number."""
    match = _ORDER_ID_RE.search(text)
    if match:
        return match.group().upper()
    match = _BARE_NUMBER_RE.search(text)
    return match.group() if match else None


def extract_discount_code(text):
    match = _DISCOUNT_CODE_RE.search(text)
    if match:
        return match.group().upper()
    if _DISCOUNT_CONTEXT_RE.search(text):
        match = _DISCOUNT_CODE_LETTERS_RE.search(text)
        if match:
            return match.group()
    return None


def extract_product_name(text):
    match = _PRODUCT_NAME_RE.search(text)
    if not match:
        return None
    name = match.group(1).strip().rstrip(",.?!")
    return name or None


def extract_email(text):
    match = _EMAIL_RE.search(text)
    return match.group() if match else None


# dateparser's fuzzy search can match ordinary phrases (e.g. "and now") as
# dates, so require a recognizable date word or numeric date in its match.
_DATE_CUE_RE = re.compile(
    r"\b(?:today|tomorrow|tonight|yesterday|"
    r"(?:next|this|coming)\s+(?:week|month|year|weekend|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"\d{1,4}[/-]\d{1,2}(?:[/-]\d{1,4})?|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"in\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:days?|weeks?|months?|years?))\b",
    re.IGNORECASE,
)


def extract_date(text):
    results = dateparser.search.search_dates(
        text, languages=["en"], settings={"PREFER_DATES_FROM": "future"}
    )
    for matched_text, parsed in results or []:
        if _DATE_CUE_RE.search(matched_text):
            return {"text": matched_text, "date": parsed.isoformat()}
    return None


# Maps slot name -> extractor function. Used by the pipeline to pull only the
# slots a given intent actually needs.
SLOT_EXTRACTORS = {
    "order_id": extract_order_id,
    "product_name": extract_product_name,
    "discount_code": extract_discount_code,
    "new_date": extract_date,
    "email": extract_email,
}
