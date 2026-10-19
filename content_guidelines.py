"""
Content guidelines — single source of truth for editorial rules.
Imported by prompt templates, compliance, and script generation.
"""

# ── Content Buckets ─────────────────────────────────────────────
# These define the approved topic categories. Topics outside these
# buckets get flagged for manual review.
CONTENT_BUCKETS = [
    "hair loss myths",
    "beginner mistakes with minoxidil",
    "microneedling basics",
    "hair transplant myths",
    "DHT and androgenic alopecia education",
    "anti-aging skincare ingredients",
    "tretinoin basics",
    "sunscreen and photoaging",
    "collagen and supplement skepticism",
    "realistic expectations and timelines",
]

# ── Target Audience ─────────────────────────────────────────────
AUDIENCE_DESCRIPTION = (
    "Men concerned about hair loss, people interested in anti-aging "
    "skincare, and beginners who want simple, evidence-aware explanations. "
    "Primarily adults 25–55. They are skeptical of hype, want facts, "
    "and appreciate honest framing of what works and what doesn't."
)

# ── Brand Voice ─────────────────────────────────────────────────
BRAND_VOICE = (
    "Educational and trustworthy, like a knowledgeable friend who "
    "actually reads the research. Concise, factual, high-retention. "
    "Never sounds like a scammy miracle-cure page or an AI-generated "
    "listicle. No cringe guru tone, no fake authority, no fearmongering."
)

# ── Hard Avoid List ─────────────────────────────────────────────
# These are content patterns to NEVER generate, beyond just banned phrases.
CONTENT_AVOID_RULES = [
    "Guaranteed or absolute medical claims of any kind",
    "Disease diagnosis or telling viewers they have a condition",
    "Fearmongering about hair loss or aging to drive panic",
    "Overpromising results from any product, treatment, or routine",
    "Fake authority — never claim to be a doctor or cite invented credentials",
    "Direct medical instructions beyond general education",
    "AI slop — generic filler language, emoji spam, or robotic phrasing",
    "Cringe guru tone — 'trust me bro,' fake enthusiasm, manufactured urgency",
    "Supplement shilling or affiliate-style product pushing",
    "Before/after claims without noting individual variation",
    "Absolute timelines ('you WILL see results in 3 months')",
]

# ── Style Rules ─────────────────────────────────────────────────
STYLE_RULES = [
    "Lead with the most interesting or surprising fact",
    "Every sentence must earn its place — cut ruthlessly",
    "Write for speech, not text — use natural cadence and short phrases",
    "Prefer 'some research suggests' over 'studies show' (less generic)",
    "Use specific numbers or examples when possible instead of vague claims",
    "End with genuine value, not a sales pitch",
    "If referencing a treatment, always note it's not for everyone",
    "Frame uncertainty as honesty, not weakness — viewers respect it",
    "Use contrast and surprise to hold attention ('most people think X, but actually Y')",
    "Never pad scripts with filler — 25 great words beat 80 mediocre ones",
]

# ── Approved Hedging Language ───────────────────────────────────
APPROVED_HEDGES = [
    "may help",
    "some evidence suggests",
    "results vary",
    "research indicates",
    "early research points to",
    "anecdotally, some people report",
    "not guaranteed, but worth knowing about",
    "talk to a dermatologist before starting",
    "individual results will differ",
    "this is education, not medical advice",
]


def get_guidelines_block() -> str:
    """
    Return a formatted text block of all guidelines,
    suitable for injecting into LLM prompts.
    """
    buckets = "\n".join(f"  - {b}" for b in CONTENT_BUCKETS)
    avoids = "\n".join(f"  - {a}" for a in CONTENT_AVOID_RULES)
    style = "\n".join(f"  - {s}" for s in STYLE_RULES)
    hedges = ", ".join(f'"{h}"' for h in APPROVED_HEDGES)

    return f"""CONTENT GUIDELINES (follow strictly):

BRAND VOICE:
{BRAND_VOICE}

TARGET AUDIENCE:
{AUDIENCE_DESCRIPTION}

APPROVED CONTENT BUCKETS:
{buckets}

NEVER DO:
{avoids}

STYLE RULES:
{style}

APPROVED HEDGING LANGUAGE (use these instead of absolute claims):
{hedges}"""
