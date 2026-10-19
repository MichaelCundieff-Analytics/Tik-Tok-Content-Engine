"""
Compliance and safety module — rewrites scripts to remove unsafe medical claims.
Uses both rule-based flagging AND LLM-powered rewriting.
"""

import json
import re
import time
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, HIGH_RISK_KEYWORDS,
    PROMPTS_DIR, MAX_RETRIES, RETRY_DELAY_SECONDS
)
from modules.logger import get_logger, log_event
from modules.content_guidelines import get_guidelines_block

log = get_logger("compliance")
client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# Hard-banned phrases — these should never appear in any output
BANNED_PHRASES = [
    "guaranteed regrowth",
    "reverses aging",
    "clinically proven",
    "100% effective",
    "miracle cure",
    "permanent results",
    "doctor recommended",       # unless citing a specific, named doctor
    "FDA approved",             # unless actually citing a real FDA approval
    "eliminates hair loss",
    "stops aging",
    "scientifically proven",
    "works for everyone",
    "you need this",
    "trust me",
    "doctors don't want you to know",
    "big pharma",
    "secret cure",
    "ancient remedy",
    "one weird trick",
    "they don't want you to know",
]

# Tone/slop patterns — flag these for rewrite even if not medically dangerous
SLOP_PHRASES = [
    "in this video",
    "let me tell you",
    "here's the thing",
    "you won't believe",
    "game changer",
    "life hack",
    "smash that like",
    "drop a comment",
    "link in bio",
]

# Replacement suggestions for common overclaims
SOFTENING_MAP = {
    "will regrow": "may help support regrowth",
    "stops hair loss": "may help reduce hair thinning",
    "reverses": "may help address",
    "proven to": "some research suggests it may",
    "guaranteed": "individual results may vary",
    "cures": "may help manage",
    "eliminates": "may help reduce",
    "permanently": "over time, with consistent use,",
    "you must": "you might want to consider",
    "always works": "may work for some people",
    "never fails": "has shown promise in some cases",
}


def check_compliance(script: str, topic: str) -> dict:
    """
    Run compliance checks on a script.

    Returns:
        {
            "is_compliant": bool,
            "flags": list[str],
            "needs_review": bool,
            "risk_level": "low" | "medium" | "high"
        }
    """
    flags = []
    needs_review = False

    # Check for banned phrases
    script_lower = script.lower()
    for phrase in BANNED_PHRASES:
        if phrase in script_lower:
            flags.append(f"BANNED: Contains '{phrase}'")

    # Check for high-risk keywords in topic
    topic_lower = topic.lower()
    for kw in HIGH_RISK_KEYWORDS:
        if kw in topic_lower:
            needs_review = True
            flags.append(f"HIGH_RISK_TOPIC: Contains keyword '{kw}'")

    # Check for slop/tone violations
    for phrase in SLOP_PHRASES:
        if phrase in script_lower:
            flags.append(f"SLOP: Contains filler/cringe phrase '{phrase}'")

    # Check for absolute claims patterns
    absolute_patterns = [
        r"\b(will|does|can)\s+(cure|fix|reverse|eliminate|stop)\b",
        r"\b(100|every|all)\s*(percent|%|people|patients)\b",
        r"\bno\s+side\s+effects\b",
        r"\brisk[\s-]*free\b",
        r"\byou\s+(need|must|have)\s+to\b",
        r"\b(always|never)\s+(works|fails)\b",
    ]
    for pattern in absolute_patterns:
        matches = re.findall(pattern, script_lower)
        if matches:
            flags.append(f"ABSOLUTE_CLAIM: Pattern '{pattern}' matched")

    # Determine risk level
    if any("BANNED" in f for f in flags):
        risk_level = "high"
    elif needs_review or len(flags) > 2:
        risk_level = "medium"
    elif flags:
        risk_level = "low"
    else:
        risk_level = "low"

    is_compliant = len(flags) == 0

    return {
        "is_compliant": is_compliant,
        "flags": flags,
        "needs_review": needs_review,
        "risk_level": risk_level,
    }


def rewrite_for_compliance(script: str, topic: str) -> dict:
    """
    Use Claude to rewrite a script with safe, cautious language.

    Returns:
        {
            "rewritten_script": str,
            "changes_made": list[str],
            "compliance_check": dict
        }
    """
    if not client:
        # Fallback: rule-based softening only
        return _rule_based_rewrite(script, topic)

    prompt_template = (PROMPTS_DIR / "compliance_rewrite.txt").read_text()
    user_prompt = prompt_template.format(
        script=script,
        topic=topic,
        banned_phrases=", ".join(BANNED_PHRASES),
        guidelines=get_guidelines_block(),
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text
            result = _parse_compliance_response(raw)

            # Verify the rewrite passes compliance
            recheck = check_compliance(result["rewritten_script"], topic)
            result["compliance_check"] = recheck

            if not recheck["is_compliant"]:
                log.warning(f"Rewrite still has issues: {recheck['flags']}")
                result["rewritten_script"] = _rule_based_soften(
                    result["rewritten_script"]
                )
                result["compliance_check"] = check_compliance(
                    result["rewritten_script"], topic
                )

            log.info(f"Compliance rewrite done for: {topic[:50]}...")
            return result

        except Exception as e:
            log.warning(f"Compliance rewrite attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                return _rule_based_rewrite(script, topic)


def _rule_based_rewrite(script: str, topic: str) -> dict:
    """Fallback: apply softening map rules without LLM."""
    rewritten = _rule_based_soften(script)
    changes = []
    for old, new in SOFTENING_MAP.items():
        if old.lower() in script.lower():
            changes.append(f"Replaced '{old}' → '{new}'")
    return {
        "rewritten_script": rewritten,
        "changes_made": changes,
        "compliance_check": check_compliance(rewritten, topic),
    }


def _rule_based_soften(text: str) -> str:
    """Apply regex-based softening to remove overclaims."""
    result = text
    for old, new in SOFTENING_MAP.items():
        result = re.sub(re.escape(old), new, result, flags=re.IGNORECASE)
    # Remove any remaining banned phrases
    for phrase in BANNED_PHRASES:
        result = re.sub(re.escape(phrase), "[REMOVED — needs rewrite]", result, flags=re.IGNORECASE)
    return result


def _parse_compliance_response(raw: str) -> dict:
    """Parse compliance rewrite response from Claude."""
    if "```json" in raw:
        json_str = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        json_str = raw.split("```")[1].split("```")[0].strip()
    else:
        json_str = raw.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        data = {
            "rewritten_script": raw.strip(),
            "changes_made": ["Full rewrite applied"],
        }

    data.setdefault("rewritten_script", raw)
    data.setdefault("changes_made", [])
    return data
