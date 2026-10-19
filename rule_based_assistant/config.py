# Deterministic rule-engine configuration for the Rule-Based Assistant.
# Deterministic rules classify intents; no model inference is used.

RETRIEVAL_TOP_K = 3
HIGH_CONFIDENCE = 0.6
MID_CONFIDENCE = 0.4

MULTI_INTENT_BLOCK_MESSAGE = (
    "It looks like you're asking about more than one thing at once ({intents}). "
    "Could you send those one at a time so I can help with each?"
)

CORRECTION_KEYWORDS = [
    "instead",
    "never mind",
    "changed my mind",
    "scratch that",
    "on second thought",
    "i meant",
    "i mean",
    "my mistake",
    "make that",
    "leave it as",
    "leave the",
    "cancel that",
    "forget that",
    "previous one",
]

REFERENCE_KEYWORDS = [
    "that one",
    "the previous",
    "the same one",
    "back to",
    "about the",
    "this order",
    "that order",
]

# -- slots.py: deterministic slot extraction --------------------------------

ORDER_ID_PREFIX = "ORD-"
BARE_NUMBER_MIN_DIGITS = 4

DISCOUNT_CODE_MIN_LEN = 4
DISCOUNT_CODE_MAX_LEN = 12
DISCOUNT_CONTEXT_KEYWORDS = ["code", "coupon", "promo", "promotion", "promotions", "discount"]

PRODUCT_NAME_CUE_WORDS = ["the", "my", "this", "that"]
PRODUCT_NAME_MIN_WORD_LEN = 2
PRODUCT_NAME_MAX_WORDS = 5
