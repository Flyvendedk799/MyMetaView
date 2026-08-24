"""Golden URL corpus for Phase 0 baseline + Phase 7 nightly regression.

The corpus is the contract for "is the demo preview engine working?". It is
stratified across the five categories called out in the plan and includes a
shadow set rotated monthly to mitigate corpus overfitting (see Risk 3 in the
plan's risk register).

Data shape is intentionally minimal: a URL plus the truth labels we score
against. The runner (``backend/scripts/preview_engine/run_corpus.py``)
materializes outputs/screenshots/logs into ``artifacts/baseline/<date>/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class GoldenCorpusCategory(str, Enum):
    """Stratified categories required by the plan."""

    SAAS_LANDING = "saas_landing"
    ECOMMERCE = "ecommerce"
    DOCS = "docs"
    CREATOR = "creator"
    LOCAL_BUSINESS = "local_business"


@dataclass
class GoldenURL:
    """A single corpus URL with manually-labeled truth signals."""

    url: str
    category: GoldenCorpusCategory
    expected_title_keywords: List[str] = field(default_factory=list)
    expected_template_type: Optional[str] = None
    expected_social_proof_present: bool = False
    notes: str = ""
    # Which writing system the page's copy is in. The corpus skewed entirely
    # Latin, which meant every typography rule was validated against the one
    # script where counting characters happens to approximate visual width.
    script: str = "latin"

    def matches_title(self, title: str) -> bool:
        """Fidelity helper: any expected keyword appears in title."""
        if not self.expected_title_keywords or not title:
            return False
        title_lower = title.lower()
        return any(kw.lower() in title_lower for kw in self.expected_title_keywords)


# 60-URL golden corpus stratified across categories.
# This is the contract the engine is judged against in CI (Phase 7).
GOLDEN_CORPUS: List[GoldenURL] = [
    # ---- SaaS landing pages (12) -----------------------------------------
    GoldenURL("https://www.notion.so", GoldenCorpusCategory.SAAS_LANDING,
              ["notion"], "saas", True, "Workspace SaaS"),
    GoldenURL("https://linear.app", GoldenCorpusCategory.SAAS_LANDING,
              ["linear"], "saas", True, "Project tracker"),
    GoldenURL("https://stripe.com", GoldenCorpusCategory.SAAS_LANDING,
              ["stripe"], "saas", True, "Payments"),
    GoldenURL("https://vercel.com", GoldenCorpusCategory.SAAS_LANDING,
              ["vercel"], "saas", True, "Hosting"),
    GoldenURL("https://www.figma.com", GoldenCorpusCategory.SAAS_LANDING,
              ["figma"], "saas", True, "Design tool"),
    GoldenURL("https://airtable.com", GoldenCorpusCategory.SAAS_LANDING,
              ["airtable"], "saas", True, "Spreadsheet/db"),
    GoldenURL("https://www.intercom.com", GoldenCorpusCategory.SAAS_LANDING,
              ["intercom"], "saas", True, "Customer support"),
    GoldenURL("https://www.dropbox.com", GoldenCorpusCategory.SAAS_LANDING,
              ["dropbox"], "saas", True, "Storage"),
    GoldenURL("https://slack.com", GoldenCorpusCategory.SAAS_LANDING,
              ["slack"], "saas", True, "Messaging"),
    GoldenURL("https://www.atlassian.com", GoldenCorpusCategory.SAAS_LANDING,
              ["atlassian"], "saas", True, "Suite"),
    GoldenURL("https://posthog.com", GoldenCorpusCategory.SAAS_LANDING,
              ["posthog"], "saas", False, "Product analytics"),
    GoldenURL("https://supabase.com", GoldenCorpusCategory.SAAS_LANDING,
              ["supabase"], "saas", True, "Backend"),

    # ---- E-commerce PDP/PLP (12) -----------------------------------------
    GoldenURL("https://www.allbirds.com", GoldenCorpusCategory.ECOMMERCE,
              ["allbirds"], "product", True, "Sustainable shoes"),
    GoldenURL("https://www.warbyparker.com", GoldenCorpusCategory.ECOMMERCE,
              ["warby parker", "warby"], "product", True, "Eyewear"),
    GoldenURL("https://www.glossier.com", GoldenCorpusCategory.ECOMMERCE,
              ["glossier"], "product", True, "Beauty"),
    GoldenURL("https://shop.tesla.com", GoldenCorpusCategory.ECOMMERCE,
              ["tesla"], "product", True, "EV merchandise"),
    GoldenURL("https://www.everlane.com", GoldenCorpusCategory.ECOMMERCE,
              ["everlane"], "product", True, "Apparel"),
    GoldenURL("https://www.harrys.com", GoldenCorpusCategory.ECOMMERCE,
              ["harry"], "product", True, "Razors"),
    GoldenURL("https://www.casper.com", GoldenCorpusCategory.ECOMMERCE,
              ["casper"], "product", True, "Mattresses"),
    GoldenURL("https://www.bombas.com", GoldenCorpusCategory.ECOMMERCE,
              ["bombas"], "product", True, "Socks"),
    GoldenURL("https://patagonia.com", GoldenCorpusCategory.ECOMMERCE,
              ["patagonia"], "product", True, "Outdoor"),
    GoldenURL("https://www.nike.com", GoldenCorpusCategory.ECOMMERCE,
              ["nike"], "product", True, "Athletic"),
    GoldenURL("https://www.lego.com", GoldenCorpusCategory.ECOMMERCE,
              ["lego"], "product", True, "Toys"),
    GoldenURL("https://www.ikea.com", GoldenCorpusCategory.ECOMMERCE,
              ["ikea"], "product", True, "Furniture"),

    # ---- Documentation pages (12) ----------------------------------------
    GoldenURL("https://react.dev/learn", GoldenCorpusCategory.DOCS,
              ["react"], "article", False, "React docs"),
    GoldenURL("https://nextjs.org/docs", GoldenCorpusCategory.DOCS,
              ["next"], "article", False, "Next.js docs"),
    GoldenURL("https://docs.python.org/3/", GoldenCorpusCategory.DOCS,
              ["python"], "article", False, "Python docs"),
    GoldenURL("https://docs.djangoproject.com/en/stable/",
              GoldenCorpusCategory.DOCS, ["django"], "article", False,
              "Django docs"),
    GoldenURL("https://kubernetes.io/docs/home/", GoldenCorpusCategory.DOCS,
              ["kubernetes"], "article", False, "K8s docs"),
    GoldenURL("https://docs.docker.com", GoldenCorpusCategory.DOCS,
              ["docker"], "article", False, "Docker docs"),
    GoldenURL("https://tailwindcss.com/docs", GoldenCorpusCategory.DOCS,
              ["tailwind"], "article", False, "Tailwind docs"),
    GoldenURL("https://docs.github.com", GoldenCorpusCategory.DOCS,
              ["github"], "article", False, "GitHub docs"),
    GoldenURL("https://developer.mozilla.org/en-US/docs/Web",
              GoldenCorpusCategory.DOCS, ["mdn", "web"], "article", False,
              "MDN"),
    GoldenURL("https://www.typescriptlang.org/docs/",
              GoldenCorpusCategory.DOCS, ["typescript"], "article", False,
              "TS docs"),
    GoldenURL("https://docs.aws.amazon.com", GoldenCorpusCategory.DOCS,
              ["aws"], "article", False, "AWS docs"),
    GoldenURL("https://learn.microsoft.com/en-us/azure/", GoldenCorpusCategory.DOCS,
              ["azure", "microsoft"], "article", False, "Azure docs"),

    # ---- Creator portfolios / blogs (12) ---------------------------------
    GoldenURL("https://paulgraham.com", GoldenCorpusCategory.CREATOR,
              ["paul graham"], "profile", False, "Essays"),
    GoldenURL("https://danabra.mov", GoldenCorpusCategory.CREATOR,
              ["dan abramov"], "profile", False, "Engineer blog"),
    GoldenURL("https://overreacted.io", GoldenCorpusCategory.CREATOR,
              ["overreacted"], "blog", False, "Personal blog"),
    GoldenURL("https://www.joshwcomeau.com", GoldenCorpusCategory.CREATOR,
              ["josh", "comeau"], "profile", False, "Designer dev"),
    GoldenURL("https://samaltman.com", GoldenCorpusCategory.CREATOR,
              ["sam altman"], "profile", False, "Sam Altman blog"),
    GoldenURL("https://patrickcollison.com", GoldenCorpusCategory.CREATOR,
              ["patrick collison"], "profile", False, "Patrick Collison"),
    GoldenURL("https://www.benkuhn.net", GoldenCorpusCategory.CREATOR,
              ["ben kuhn"], "profile", False, "Engineering writer"),
    GoldenURL("https://blog.cloudflare.com", GoldenCorpusCategory.CREATOR,
              ["cloudflare"], "blog", False, "Eng blog"),
    GoldenURL("https://blog.replit.com", GoldenCorpusCategory.CREATOR,
              ["replit"], "blog", False, "Replit blog"),
    GoldenURL("https://www.gwern.net", GoldenCorpusCategory.CREATOR,
              ["gwern"], "profile", False, "Researcher"),
    GoldenURL("https://www.lennysnewsletter.com", GoldenCorpusCategory.CREATOR,
              ["lenny"], "blog", True, "Newsletter"),
    GoldenURL("https://every.to", GoldenCorpusCategory.CREATOR,
              ["every"], "blog", True, "Newsletter network"),

    # ---- Local business pages (12) ---------------------------------------
    GoldenURL("https://www.bluebottlecoffee.com",
              GoldenCorpusCategory.LOCAL_BUSINESS,
              ["blue bottle"], "landing", True, "Coffee chain"),
    GoldenURL("https://www.shakeshack.com", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["shake shack"], "landing", True, "Burger chain"),
    GoldenURL("https://www.sweetgreen.com", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["sweetgreen"], "landing", True, "Salad chain"),
    GoldenURL("https://www.chipotle.com", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["chipotle"], "landing", True, "Restaurant"),
    GoldenURL("https://www.toptable.com", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["toptable"], "landing", False, "Restaurant booking"),
    GoldenURL("https://www.opentable.com", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["opentable"], "landing", True, "Restaurants"),
    GoldenURL("https://www.airbnb.com", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["airbnb"], "landing", True, "Lodging"),
    GoldenURL("https://www.peet's.com", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["peet"], "landing", True, "Coffee"),
    GoldenURL("https://www.classpass.com", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["classpass"], "landing", True, "Fitness"),
    GoldenURL("https://www.massageenvy.com",
              GoldenCorpusCategory.LOCAL_BUSINESS,
              ["massage envy"], "landing", True, "Wellness"),
    GoldenURL("https://www.solidcore.co", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["solidcore", "[solidcore]"], "landing", True, "Fitness studio"),
    GoldenURL("https://www.barrysbootcamp.com",
              GoldenCorpusCategory.LOCAL_BUSINESS,
              ["barry"], "landing", True, "Fitness studio"),
]


# Shadow corpus rotated monthly to mitigate overfitting (see plan Risk 3).
# 20% the size of the golden corpus, drawn from the same five strata.
SHADOW_CORPUS: List[GoldenURL] = [
    GoldenURL("https://www.zoom.us", GoldenCorpusCategory.SAAS_LANDING,
              ["zoom"], "saas", True, "Shadow"),
    GoldenURL("https://www.miro.com", GoldenCorpusCategory.SAAS_LANDING,
              ["miro"], "saas", True, "Shadow"),
    GoldenURL("https://www.calendly.com", GoldenCorpusCategory.SAAS_LANDING,
              ["calendly"], "saas", True, "Shadow"),
    GoldenURL("https://www.outdoorvoices.com", GoldenCorpusCategory.ECOMMERCE,
              ["outdoor voices"], "product", True, "Shadow"),
    GoldenURL("https://www.aesop.com", GoldenCorpusCategory.ECOMMERCE,
              ["aesop"], "product", True, "Shadow"),
    GoldenURL("https://www.gymshark.com", GoldenCorpusCategory.ECOMMERCE,
              ["gymshark"], "product", True, "Shadow"),
    GoldenURL("https://docs.fastapi.tiangolo.com", GoldenCorpusCategory.DOCS,
              ["fastapi"], "article", False, "Shadow"),
    GoldenURL("https://docs.rs", GoldenCorpusCategory.DOCS,
              ["docs.rs", "rust"], "article", False, "Shadow"),
    GoldenURL("https://kentcdodds.com", GoldenCorpusCategory.CREATOR,
              ["kent c", "dodds"], "profile", False, "Shadow"),
    GoldenURL("https://swyx.io", GoldenCorpusCategory.CREATOR,
              ["swyx", "shawn"], "profile", False, "Shadow"),
    GoldenURL("https://www.starbucks.com",
              GoldenCorpusCategory.LOCAL_BUSINESS, ["starbucks"], "landing",
              True, "Shadow"),
    GoldenURL("https://www.dunkindonuts.com",
              GoldenCorpusCategory.LOCAL_BUSINESS, ["dunkin"], "landing",
              True, "Shadow"),
]


# ---- Non-Latin scripts (12) ------------------------------------------------
# The typography rules — headline sizing, truncation, line breaking, direction —
# are all width-based rather than character-based, and this is the slice that
# proves it. CJK is twice as wide per glyph, Arabic and Hebrew read the other
# way, and German compounds are single tokens wider than the column: three
# different ways for a character-count rule to be wrong.
I18N_CORPUS: List[GoldenURL] = [
    GoldenURL("https://www.rakuten.co.jp", GoldenCorpusCategory.ECOMMERCE,
              ["楽天", "rakuten"], "product", True, "Japanese e-commerce", "cjk"),
    GoldenURL("https://www.nintendo.co.jp", GoldenCorpusCategory.SAAS_LANDING,
              ["任天堂", "nintendo"], "landing", False, "Japanese corporate", "cjk"),
    GoldenURL("https://www.sony.jp", GoldenCorpusCategory.ECOMMERCE,
              ["sony", "ソニー"], "product", False, "Japanese product", "cjk"),
    GoldenURL("https://www.naver.com", GoldenCorpusCategory.SAAS_LANDING,
              ["naver", "네이버"], "landing", False, "Korean portal", "cjk"),
    GoldenURL("https://www.kakaocorp.com", GoldenCorpusCategory.SAAS_LANDING,
              ["kakao", "카카오"], "landing", False, "Korean corporate", "cjk"),
    GoldenURL("https://www.alibaba.com", GoldenCorpusCategory.ECOMMERCE,
              ["alibaba"], "product", True, "Chinese marketplace", "cjk"),
    GoldenURL("https://www.aljazeera.net", GoldenCorpusCategory.DOCS,
              ["الجزيرة", "aljazeera"], "article", False, "Arabic news (RTL)", "arabic"),
    GoldenURL("https://www.emirates.com/ae/arabic/",
              GoldenCorpusCategory.LOCAL_BUSINESS,
              ["emirates", "طيران"], "landing", False, "Arabic airline (RTL)", "arabic"),
    GoldenURL("https://www.calcalist.co.il", GoldenCorpusCategory.DOCS,
              ["כלכליסט", "calcalist"], "article", False, "Hebrew business news (RTL)", "hebrew"),
    GoldenURL("https://www.sap.com/germany/index.html",
              GoldenCorpusCategory.SAAS_LANDING,
              ["sap"], "saas", True, "German compounds", "latin-long"),
    GoldenURL("https://www.allianz.de", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["allianz"], "landing", True, "German insurance compounds", "latin-long"),
    GoldenURL("https://www.bahn.de", GoldenCorpusCategory.LOCAL_BUSINESS,
              ["bahn", "deutsche"], "landing", False, "German rail compounds", "latin-long"),
]


def get_corpus(include_shadow: bool = False) -> List[GoldenURL]:
    """Return the corpus, optionally including the shadow rotation.

    The i18n slice is part of the main corpus rather than an extra: a
    typography change that breaks CJK should fail the ordinary run, not a run
    somebody has to remember to ask for.
    """
    base = GOLDEN_CORPUS + I18N_CORPUS
    return base + SHADOW_CORPUS if include_shadow else base


def get_corpus_by_category(
    category: GoldenCorpusCategory,
    include_shadow: bool = False,
) -> List[GoldenURL]:
    """Filter the corpus to a single category."""
    pool = get_corpus(include_shadow=include_shadow)
    return [u for u in pool if u.category == category]


def get_corpus_by_script(script: str, include_shadow: bool = False) -> List[GoldenURL]:
    """The URLs written in one script — the i18n regression slice."""
    return [u for u in get_corpus(include_shadow=include_shadow) if u.script == script]


def script_counts(include_shadow: bool = False) -> Dict[str, int]:
    """How many URLs per writing system, for stratification checks."""
    counts: Dict[str, int] = {}
    for entry in get_corpus(include_shadow=include_shadow):
        counts[entry.script] = counts.get(entry.script, 0) + 1
    return counts


def category_counts(include_shadow: bool = False) -> Dict[str, int]:
    """For sanity-checking stratification at runtime."""
    counts: Dict[str, int] = {}
    for entry in get_corpus(include_shadow=include_shadow):
        counts[entry.category.value] = counts.get(entry.category.value, 0) + 1
    return counts
