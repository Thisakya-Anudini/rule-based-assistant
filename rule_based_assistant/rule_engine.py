import re

from .intents import INTENTS


def normalize_text(text):
    if text is None:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _contains_phrase(text, phrase):
    return normalize_text(phrase) in normalize_text(text)


def _contains_any(text, terms):
    normalized = normalize_text(text)
    return any(
        re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized)
        for normalized_term in (normalize_text(term) for term in terms if term)
    )


def _contains_all(text, terms):
    normalized = normalize_text(text)
    return all(normalize_text(term) in normalized for term in terms if term)


def _regex_match(text, pattern):
    return bool(re.search(pattern, normalize_text(text), flags=re.IGNORECASE))


def _score_rule(kind, text, rule, matched):
    if kind == "phrase":
        if _contains_phrase(text, rule["value"]):
            matched.append(rule["label"])
            return float(rule["weight"])
    elif kind == "keyword":
        if _contains_any(text, rule["terms"]):
            matched.append(rule["label"])
            return float(rule["weight"])
    elif kind == "combo":
        if _contains_all(text, rule["terms"]):
            matched.append(rule["label"])
            return float(rule["weight"])
    elif kind == "regex":
        if _regex_match(text, rule["pattern"]):
            matched.append(rule["label"])
            return float(rule["weight"])
    return 0.0


INTENT_RULES = {
    "track_order": [
        {"kind": "phrase", "value": "where is my order", "weight": 1.0, "label": "phrase:where is my order"},
        {"kind": "phrase", "value": "track my order", "weight": 1.0, "label": "phrase:track my order"},
        {"kind": "phrase", "value": "track my package", "weight": 0.95, "label": "phrase:track my package"},
        {"kind": "phrase", "value": "order number", "weight": 0.7, "label": "phrase:order number"},
        {"kind": "keyword", "terms": ["track", "tracking"], "weight": 0.55, "label": "keyword:track_action"},
        {"kind": "phrase", "value": "hasn't arrived", "weight": 0.6, "label": "phrase:hasn_t_arrived"},
        {"kind": "combo", "terms": ["order", "track"], "weight": 0.9, "label": "keyword_combination: order + track"},
        {"kind": "combo", "terms": ["package", "track"], "weight": 0.85, "label": "keyword_combination: package + track"},
        {"kind": "combo", "terms": ["order", "status"], "weight": 0.75, "label": "keyword_combination: order + status"},
        {"kind": "combo", "terms": ["shipment", "status"], "weight": 0.75, "label": "keyword_combination: shipment + status"},
        {"kind": "combo", "terms": ["order", "arrived"], "weight": 0.45, "label": "keyword_combination: order + arrived"},
        {"kind": "keyword", "terms": ["tracking", "where", "arrival", "delivered"], "weight": 0.35, "label": "keyword:track_support"},
    ],
    "cancel_order": [
        {"kind": "phrase", "value": "cancel my order", "weight": 1.0, "label": "phrase:cancel my order"},
        {"kind": "phrase", "value": "cancel order", "weight": 0.95, "label": "phrase:cancel order"},
        {"kind": "phrase", "value": "stop my order", "weight": 0.95, "label": "phrase:stop my order"},
        {"kind": "keyword", "terms": ["cancel", "cancelled", "canceled"], "weight": 0.55, "label": "keyword:cancel_action"},
        {"kind": "combo", "terms": ["order", "cancel"], "weight": 0.9, "label": "keyword_combination: order + cancel"},
        {"kind": "combo", "terms": ["order", "stop"], "weight": 0.85, "label": "keyword_combination: order + stop"},
        {"kind": "keyword", "terms": ["cancelled", "canceled", "terminate", "revoke"], "weight": 0.4, "label": "keyword:cancel_support"},
    ],
    "modify_order": [
        {"kind": "phrase", "value": "change my order", "weight": 0.9, "label": "phrase:change my order"},
        {"kind": "combo", "terms": ["order", "change"], "weight": 0.8, "label": "keyword_combination: order + change"},
        {"kind": "combo", "terms": ["order", "update"], "weight": 0.85, "label": "keyword_combination: order + update"},
        {"kind": "combo", "terms": ["address", "order"], "weight": 0.75, "label": "keyword_combination: address + order"},
        {"kind": "combo", "terms": ["size", "order"], "weight": 0.75, "label": "keyword_combination: size + order"},
        {"kind": "combo", "terms": ["color", "order"], "weight": 0.75, "label": "keyword_combination: color + order"},
        {"kind": "keyword", "terms": ["add item", "combine orders", "merge order", "shipping address"], "weight": 0.45, "label": "keyword:modify_support"},
    ],
    "change_delivery_date": [
        {"kind": "phrase", "value": "change my delivery date", "weight": 0.95, "label": "phrase:change my delivery date"},
        {"kind": "phrase", "value": "reschedule my delivery", "weight": 0.9, "label": "phrase:reschedule my delivery"},
        {"kind": "phrase", "value": "reschedule", "weight": 0.65, "label": "phrase:reschedule"},
        {"kind": "combo", "terms": ["delivery", "date"], "weight": 0.9, "label": "keyword_combination: delivery + date"},
        {"kind": "combo", "terms": ["reschedule", "delivery"], "weight": 0.9, "label": "keyword_combination: reschedule + delivery"},
        {"kind": "combo", "terms": ["move", "delivery"], "weight": 0.7, "label": "keyword_combination: move + delivery"},
        {"kind": "keyword", "terms": ["next week", "tomorrow", "delivery day"], "weight": 0.4, "label": "keyword:delivery_date_support"},
    ],
    "report_delivery_problem": [
        {"kind": "phrase", "value": "package arrived damaged", "weight": 0.95, "label": "phrase:package arrived damaged"},
        {"kind": "phrase", "value": "it says delivered but i never got it", "weight": 0.95, "label": "phrase:delivered but never got it"},
        {"kind": "phrase", "value": "hasn't arrived", "weight": 0.75, "label": "phrase:hasn_t_arrived_issue"},
        {"kind": "combo", "terms": ["damaged", "package"], "weight": 0.9, "label": "keyword_combination: damaged + package"},
        {"kind": "combo", "terms": ["wrong", "item"], "weight": 0.8, "label": "keyword_combination: wrong + item"},
        {"kind": "combo", "terms": ["missing", "order"], "weight": 0.8, "label": "keyword_combination: missing + order"},
        {"kind": "combo", "terms": ["order", "arrived"], "weight": 0.65, "label": "keyword_combination: order + arrived"},
        {"kind": "keyword", "terms": ["never arrived", "not arrived", "wrong address", "delivered", "missing package"], "weight": 0.45, "label": "keyword:delivery_issue_support"},
    ],
    "payment_declined": [
        {"kind": "phrase", "value": "card was declined", "weight": 1.0, "label": "phrase:card was declined"},
        {"kind": "phrase", "value": "payment failed", "weight": 0.9, "label": "phrase:payment failed"},
        {"kind": "combo", "terms": ["card", "declined"], "weight": 0.9, "label": "keyword_combination: card + declined"},
        {"kind": "combo", "terms": ["payment", "declined"], "weight": 0.85, "label": "keyword_combination: payment + declined"},
        {"kind": "keyword", "terms": ["checkout", "rejected", "payment failed", "failed at checkout"], "weight": 0.4, "label": "keyword:payment_decline_support"},
    ],
    "payment_info": [
        {"kind": "phrase", "value": "what payment methods do you accept", "weight": 1.0, "label": "phrase:what payment methods do you accept"},
        {"kind": "phrase", "value": "do you accept paypal", "weight": 0.9, "label": "phrase:accept paypal"},
        {"kind": "combo", "terms": ["payment", "methods"], "weight": 0.8, "label": "keyword_combination: payment + methods"},
        {"kind": "combo", "terms": ["gift", "card"], "weight": 0.75, "label": "keyword_combination: gift + card"},
        {"kind": "keyword", "terms": ["paypal", "apple pay", "split payment", "charged", "payment options"], "weight": 0.35, "label": "keyword:payment_info_support"},
    ],
    "billing_dispute": [
        {"kind": "phrase", "value": "charged twice", "weight": 1.0, "label": "phrase:charged twice"},
        {"kind": "phrase", "value": "incorrect charge", "weight": 0.9, "label": "phrase:incorrect charge"},
        {"kind": "combo", "terms": ["charged", "twice"], "weight": 0.9, "label": "keyword_combination: charged + twice"},
        {"kind": "combo", "terms": ["charge", "statement"], "weight": 0.8, "label": "keyword_combination: charge + statement"},
        {"kind": "keyword", "terms": ["overcharged", "duplicate charge", "billing", "refund dispute"], "weight": 0.4, "label": "keyword:billing_dispute_support"},
    ],
    "request_invoice": [
        {"kind": "phrase", "value": "copy of my receipt", "weight": 0.9, "label": "phrase:copy of my receipt"},
        {"kind": "phrase", "value": "need an invoice", "weight": 0.9, "label": "phrase:need an invoice"},
        {"kind": "combo", "terms": ["receipt", "order"], "weight": 0.8, "label": "keyword_combination: receipt + order"},
        {"kind": "combo", "terms": ["invoice", "order"], "weight": 0.8, "label": "keyword_combination: invoice + order"},
        {"kind": "keyword", "terms": ["receipt", "invoice", "itemized", "breakdown of charges"], "weight": 0.35, "label": "keyword:invoice_support"},
    ],
    "check_product_availability": [
        {"kind": "phrase", "value": "in stock", "weight": 0.9, "label": "phrase:in stock"},
        {"kind": "phrase", "value": "back in stock", "weight": 0.95, "label": "phrase:back in stock"},
        {"kind": "combo", "terms": ["available", "product"], "weight": 0.8, "label": "keyword_combination: available + product"},
        {"kind": "combo", "terms": ["in", "stock"], "weight": 0.75, "label": "keyword_combination: in + stock"},
        {"kind": "keyword", "terms": ["available", "left", "back soon", "coming back"], "weight": 0.4, "label": "keyword:availability_support"},
    ],
    "product_information": [
        {"kind": "phrase", "value": "what are the dimensions", "weight": 0.95, "label": "phrase:what are the dimensions"},
        {"kind": "phrase", "value": "what material is it made of", "weight": 0.9, "label": "phrase:what material is it made of"},
        {"kind": "combo", "terms": ["dimensions", "product"], "weight": 0.8, "label": "keyword_combination: dimensions + product"},
        {"kind": "combo", "terms": ["material", "made"], "weight": 0.75, "label": "keyword_combination: material + made"},
        {"kind": "keyword", "terms": ["dimensions", "material", "warranty", "reviews", "specs"], "weight": 0.35, "label": "keyword:product_info_support"},
    ],
    "return_policy_info": [
        {"kind": "phrase", "value": "return policy", "weight": 1.0, "label": "phrase:return policy"},
        {"kind": "phrase", "value": "how long do i have to return", "weight": 0.9, "label": "phrase:how long to return"},
        {"kind": "combo", "terms": ["return", "policy"], "weight": 0.85, "label": "keyword_combination: return + policy"},
        {"kind": "combo", "terms": ["return", "shipping"], "weight": 0.8, "label": "keyword_combination: return + shipping"},
        {"kind": "keyword", "terms": ["return window", "return shipping", "exchange policy", "clearance item"], "weight": 0.4, "label": "keyword:return_policy_support"},
    ],
    "initiate_return": [
        {"kind": "phrase", "value": "start a return", "weight": 0.95, "label": "phrase:start a return"},
        {"kind": "phrase", "value": "i want to return", "weight": 0.9, "label": "phrase:i want to return"},
        {"kind": "combo", "terms": ["return", "item"], "weight": 0.85, "label": "keyword_combination: return + item"},
        {"kind": "keyword", "terms": ["send back", "returning", "return this item"], "weight": 0.4, "label": "keyword:return_support"},
    ],
    "check_refund_status": [
        {"kind": "phrase", "value": "where is my refund", "weight": 1.0, "label": "phrase:where is my refund"},
        {"kind": "phrase", "value": "how long will the refund take", "weight": 0.95, "label": "phrase:refund duration"},
        {"kind": "phrase", "value": "refund hasn't shown up", "weight": 0.9, "label": "phrase:refund hasn't shown up"},
        {"kind": "combo", "terms": ["refund", "status"], "weight": 0.85, "label": "keyword_combination: refund + status"},
        {"kind": "keyword", "terms": ["refund", "money back"], "weight": 0.4, "label": "keyword:refund_support"},
    ],
    "exchange_item": [
        {"kind": "phrase", "value": "exchange this for a different size", "weight": 0.95, "label": "phrase:exchange for different size"},
        {"kind": "phrase", "value": "swap this item", "weight": 0.9, "label": "phrase:swap this item"},
        {"kind": "combo", "terms": ["exchange", "item"], "weight": 0.85, "label": "keyword_combination: exchange + item"},
        {"kind": "keyword", "terms": ["exchange", "swap", "different size"], "weight": 0.4, "label": "keyword:exchange_support"},
    ],
    "check_current_promotions": [
        {"kind": "phrase", "value": "any discount codes right now", "weight": 0.95, "label": "phrase:any discount codes right now"},
        {"kind": "phrase", "value": "what deals do you currently have", "weight": 0.9, "label": "phrase:what deals do you currently have"},
        {"kind": "combo", "terms": ["discount", "code"], "weight": 0.85, "label": "keyword_combination: discount + code"},
        {"kind": "keyword", "terms": ["promotion", "promo", "deal", "coupon"], "weight": 0.35, "label": "keyword:promotion_support"},
    ],
    "promo_code_issue": [
        {"kind": "phrase", "value": "promo code is not working", "weight": 0.95, "label": "phrase:promo code is not working"},
        {"kind": "phrase", "value": "discount code won't apply", "weight": 0.9, "label": "phrase:discount code won't apply"},
        {"kind": "combo", "terms": ["promo", "code"], "weight": 0.85, "label": "keyword_combination: promo + code"},
        {"kind": "combo", "terms": ["discount", "code"], "weight": 0.85, "label": "keyword_combination: discount + code"},
        {"kind": "keyword", "terms": ["won't apply", "can't use", "stack", "promo issue"], "weight": 0.4, "label": "keyword:promo_issue_support"},
    ],
    "loyalty_program_info": [
        {"kind": "phrase", "value": "do you have a loyalty program", "weight": 0.95, "label": "phrase:loyalty program"},
        {"kind": "phrase", "value": "how do i redeem my rewards points", "weight": 0.9, "label": "phrase:redeem rewards points"},
        {"kind": "combo", "terms": ["loyalty", "points"], "weight": 0.85, "label": "keyword_combination: loyalty + points"},
        {"kind": "keyword", "terms": ["rewards", "points", "loyalty"], "weight": 0.35, "label": "keyword:loyalty_support"},
    ],
    "price_match_request": [
        {"kind": "phrase", "value": "price match", "weight": 1.0, "label": "phrase:price match"},
        {"kind": "phrase", "value": "found it cheaper elsewhere", "weight": 0.85, "label": "phrase:cheaper elsewhere"},
        {"kind": "combo", "terms": ["price", "match"], "weight": 0.85, "label": "keyword_combination: price + match"},
        {"kind": "keyword", "terms": ["cheaper", "competitor", "match price"], "weight": 0.4, "label": "keyword:price_match_support"},
    ],
    "account_management": [
        {"kind": "phrase", "value": "reset my password", "weight": 0.95, "label": "phrase:reset my password"},
        {"kind": "phrase", "value": "update my email", "weight": 0.9, "label": "phrase:update my email"},
        {"kind": "combo", "terms": ["password", "reset"], "weight": 0.85, "label": "keyword_combination: password + reset"},
        {"kind": "combo", "terms": ["order", "history"], "weight": 0.8, "label": "keyword_combination: order + history"},
        {"kind": "keyword", "terms": ["account", "email", "verification", "shipping address", "delete account"], "weight": 0.35, "label": "keyword:account_support"},
    ],
    "website_technical_issue": [
        {"kind": "phrase", "value": "checkout page keeps freezing", "weight": 0.95, "label": "phrase:checkout page freezing"},
        {"kind": "phrase", "value": "can't add to cart", "weight": 0.9, "label": "phrase:can't add to cart"},
        {"kind": "combo", "terms": ["checkout", "freezing"], "weight": 0.85, "label": "keyword_combination: checkout + freezing"},
        {"kind": "combo", "terms": ["cart", "add"], "weight": 0.8, "label": "keyword_combination: cart + add"},
        {"kind": "keyword", "terms": ["bug", "error", "page hangs", "technical issue", "not loading"], "weight": 0.4, "label": "keyword:website_issue_support"},
    ],
    "gift_card_inquiry": [
        {"kind": "phrase", "value": "buy a gift card", "weight": 0.95, "label": "phrase:buy a gift card"},
        {"kind": "phrase", "value": "check my gift card balance", "weight": 0.95, "label": "phrase:check gift card balance"},
        {"kind": "combo", "terms": ["gift", "card"], "weight": 0.85, "label": "keyword_combination: gift + card"},
        {"kind": "keyword", "terms": ["gift wrapping", "gift card", "balance"], "weight": 0.35, "label": "keyword:gift_card_support"},
    ],
    "request_human_agent": [
        {"kind": "phrase", "value": "talk to a real person", "weight": 0.95, "label": "phrase:talk to a real person"},
        {"kind": "phrase", "value": "speak with a human agent", "weight": 0.95, "label": "phrase:speak with a human agent"},
        {"kind": "phrase", "value": "speak to a supervisor", "weight": 0.95, "label": "phrase:speak to a supervisor"},
        {"kind": "phrase", "value": "speak to a real person", "weight": 0.95, "label": "phrase:speak to a real person"},
        {"kind": "phrase", "value": "transfer you to a senior agent", "weight": 0.95, "label": "phrase:transfer to senior agent"},
        {"kind": "combo", "terms": ["human", "agent"], "weight": 0.9, "label": "keyword_combination: human + agent"},
        {"kind": "keyword", "terms": ["real person", "human", "transfer to agent"], "weight": 0.35, "label": "keyword:human_agent_support"},
    ],
    "file_complaint": [
        {"kind": "phrase", "value": "file a complaint", "weight": 0.95, "label": "phrase:file a complaint"},
        {"kind": "phrase", "value": "formal complaint", "weight": 0.95, "label": "phrase:formal complaint"},
        {"kind": "phrase", "value": "i want to escalate this", "weight": 0.9, "label": "phrase:escalate this"},
        {"kind": "combo", "terms": ["complaint", "issue"], "weight": 0.8, "label": "keyword_combination: complaint + issue"},
        {"kind": "keyword", "terms": ["complaint", "escalate", "awful", "terrible experience"], "weight": 0.4, "label": "keyword:complaint_support"},
    ],
    "lookup_crm_record": [
        {"kind": "phrase", "value": "pull up my account using my email", "weight": 1.0, "label": "phrase:pull up account with email"},
        {"kind": "phrase", "value": "look up my info using my email", "weight": 1.0, "label": "phrase:look up info using email"},
        {"kind": "phrase", "value": "look me up", "weight": 0.95, "label": "phrase:look me up"},
        {"kind": "phrase", "value": "look up my account", "weight": 0.9, "label": "phrase:look up my account"},
        {"kind": "combo", "terms": ["email", "lookup"], "weight": 0.9, "label": "keyword_combination: email + lookup"},
        {"kind": "keyword", "terms": ["my email", "search my account", "crm"], "weight": 0.35, "label": "keyword:lookup_support"},
    ],
}

NEGATIVE_RULES = {
    "track_order": [
        {"kind": "keyword", "terms": ["cancel", "cancelled", "stop order", "return item"], "weight": -0.35, "label": "negative:cancel_opposes_track_order"},
        {"kind": "keyword", "terms": ["damaged", "wrong item", "missing package"], "weight": -0.25, "label": "negative:delivery_issue_opposes_track_order"},
    ],
    "cancel_order": [
        {"kind": "keyword", "terms": ["status", "where", "tracking", "arrived"], "weight": -0.25, "label": "negative:tracking_opposes_cancel_order"},
    ],
    "report_delivery_problem": [
        {"kind": "keyword", "terms": ["track", "where is", "status"], "weight": -0.25, "label": "negative:status_lookup_opposes_delivery_issue"},
    ],
    "billing_dispute": [
        {"kind": "phrase", "value": "submitting a refund request", "weight": -0.9, "label": "negative:refund_submission_is_not_billing_dispute"},
    ],
    "check_refund_status": [
        {"kind": "phrase", "value": "you'll see the refund", "weight": -0.9, "label": "negative:refund_timing_is_not_status_request"},
        {"kind": "phrase", "value": "submitting a refund request", "weight": -0.9, "label": "negative:refund_submission_is_not_status_request"},
    ],
}


def _rule_hits_for_intent(text, intent_name):
    rules = INTENT_RULES.get(intent_name, [])
    matches = []
    score = 0.0
    for rule in rules:
        score += _score_rule(rule["kind"], text, rule, matches)
    for rule in NEGATIVE_RULES.get(intent_name, []):
        delta = _score_rule(rule["kind"], text, rule, matches)
        score += delta
    score = max(0.0, min(1.0, score))
    return score, matches


def score_intents(utterance):
    text = normalize_text(utterance)
    results = {}
    rule_hits = {}

    for intent_name in INTENTS:
        score, matches = _rule_hits_for_intent(text, intent_name)
        if score > 0.0:
            results[intent_name] = round(score, 3)
            rule_hits[intent_name] = matches

    return results, rule_hits


def retrieve_intents(utterance, top_k=3):
    scores, _ = score_intents(utterance)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return ranked[:top_k]


def _is_multiple_intent(utterance, candidates):
    text = normalize_text(utterance)
    clauses = [part.strip() for part in re.split(r"\b(?:and|also|plus|together|then)\b", text) if part.strip()]
    if len(clauses) < 2:
        return False

    clause_intents = []
    for clause in clauses:
        scores = [
            (intent_name, _rule_hits_for_intent(clause, intent_name)[0])
            for intent_name in INTENTS
        ]
        best_intent, best_score = max(scores, key=lambda item: item[1])
        if best_score >= 0.35:
            clause_intents.append(best_intent)

    return len(set(clause_intents)) >= 2


def classify_utterance(utterance):
    scores, rule_hits = score_intents(utterance)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return {
            "intent": "unknown_intent",
            "score": 0.0,
            "candidates": [],
            "matched_rules": [],
            "decision_type": "unknown_intent",
            "message": "No deterministic rule matched strongly enough.",
            "rule_hits": {},
        }

    if _is_multiple_intent(utterance, ranked):
        candidate_names = [name for name, _ in ranked[:2]]
        return {
            "intent": "multiple_intents",
            "score": ranked[0][1],
            "candidates": ranked[:2],
            "matched_rules": rule_hits.get(ranked[0][0], []),
            "decision_type": "multiple_intents",
            "message": "It looks like you're asking about more than one thing at once.",
            "rule_hits": {name: rule_hits.get(name, []) for name in candidate_names},
        }

    top_intent, top_score = ranked[0]
    second_intent, second_score = (ranked[1] if len(ranked) > 1 else (None, 0.0))

    if top_score < 0.35:
        return {
            "intent": "unknown_intent",
            "score": top_score,
            "candidates": ranked,
            "matched_rules": rule_hits.get(top_intent, []),
            "decision_type": "unknown_intent",
            "message": "No sufficient rule match was found.",
            "rule_hits": {name: rule_hits.get(name, []) for name, _ in ranked},
        }

    if second_intent and (top_score - second_score) < 0.12 and second_score >= 0.3:
        candidates = [(name, score) for name, score in ranked[:2]]
        return {
            "intent": "clarification_required",
            "score": top_score,
            "candidates": candidates,
            "matched_rules": rule_hits.get(top_intent, []),
            "decision_type": "clarification_required",
            "message": "The message matches more than one intent closely enough that a deterministic clarification is safer.",
            "rule_hits": {name: rule_hits.get(name, []) for name, _ in candidates},
        }

    return {
        "intent": top_intent,
        "score": top_score,
        "candidates": ranked,
        "matched_rules": rule_hits.get(top_intent, []),
        "decision_type": "rule_match",
        "message": None,
        "rule_hits": {name: rule_hits.get(name, []) for name, _ in ranked},
    }
