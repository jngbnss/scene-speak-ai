"""Deterministic slot and intent extraction driven by the scene's alias lists."""

import re
from dataclasses import dataclass, field

from app.scenes.models import Scene

_TOKEN_RE = re.compile(r"[a-z0-9']+|[.,!?;:]")

# Words that may sit in front of a drink name without changing what the drink is.
# Anything else directly before a drink alias ("pumpkin spice latte") marks an off-menu item.
STOPWORDS = frozenset(
    """
    a an the one two three some any my your our their this that these those it its
    i i'd i'll i'm me we you can could would will may might please just then also too
    and or but with of for to get have want like take order need make try give
    instead actually maybe um uh oh okay ok hi hello hey so well another same more
    coffee drink cup usual today now here thanks thank is be
    """.split()
)

NEGATIONS = frozenset({"not", "don't", "isn't", "never"})

NUMBER_WORDS = {"no": 0, "zero": 0, "a": 1, "an": 1, "one": 1, "1": 1, "two": 2, "2": 2}


@dataclass(frozen=True)
class Token:
    text: str
    is_word: bool


@dataclass(frozen=True)
class _Match:
    start: int
    end: int  # exclusive
    category: str
    value: str | None


@dataclass
class Extraction:
    slots: dict[str, str | int] = field(default_factory=dict)
    unknown_item: str | None = None
    intents: set[str] = field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        return not self.slots and self.unknown_item is None and not self.intents


def tokenize(text: str) -> list[Token]:
    normalized = text.lower().replace("’", "'")
    return [Token(t, t[0].isalnum()) for t in _TOKEN_RE.findall(normalized)]


def _phrase_tokens(phrase: str) -> tuple[str, ...]:
    return tuple(t.text for t in tokenize(phrase))


def _find(tokens: list[Token], phrase: tuple[str, ...]) -> list[int]:
    n = len(phrase)
    return [
        i
        for i in range(len(tokens) - n + 1)
        if all(tokens[i + k].is_word and tokens[i + k].text == phrase[k] for k in range(n))
    ]


class RuleExtractor:
    def __init__(self, scene: Scene) -> None:
        menu = scene.menu
        lexicon: list[tuple[str, str | None, tuple[str, ...]]] = []
        for drink in menu.drinks:
            lexicon += [("drink", drink.id, _phrase_tokens(a)) for a in drink.aliases]
        for category, options in (
            ("size", menu.sizes),
            ("temperature", menu.temperatures),
            ("milk", menu.milks),
        ):
            for option in options:
                lexicon += [(category, option.id, _phrase_tokens(a)) for a in option.aliases]
        lexicon += [("extra_shots", None, _phrase_tokens(a)) for a in menu.extra_shots.aliases]
        lexicon += [("off_menu", term, _phrase_tokens(term)) for term in scene.off_menu_terms]
        # Longest aliases first so "hot chocolate" wins over "hot" and "cold brew" over "cold".
        self._lexicon = sorted(lexicon, key=lambda e: len(e[2]), reverse=True)
        self._intents = {
            name: [_phrase_tokens(p) for p in getattr(scene.intents, name)]
            for name in ("cancel", "done", "deny", "confirm")
        }
        self._max_shots = menu.extra_shots.max

    def _menu_matches(self, tokens: list[Token]) -> list[_Match]:
        taken: set[int] = set()
        matches: list[_Match] = []
        for category, value, phrase in self._lexicon:
            for start in _find(tokens, phrase):
                span = set(range(start, start + len(phrase)))
                if span & taken:
                    continue
                taken |= span
                matches.append(_Match(start, start + len(phrase), category, value))
        return sorted(matches, key=lambda m: m.start)

    @staticmethod
    def _unknown_prefix(tokens: list[Token], match: _Match, covered: set[int]) -> list[str]:
        words: list[str] = []
        i = match.start - 1
        while i >= 0 and tokens[i].is_word and i not in covered and tokens[i].text not in STOPWORDS:
            words.insert(0, tokens[i].text)
            i -= 1
        return words

    def _shot_count(self, tokens: list[Token], match: _Match) -> int:
        for i in (match.start - 1, match.start - 2):
            if i >= 0 and tokens[i].text in NUMBER_WORDS:
                return min(NUMBER_WORDS[tokens[i].text], self._max_shots)
        return 1

    def _intents_in(self, tokens: list[Token]) -> set[str]:
        word_index = {}
        for i, t in enumerate(tokens):
            if t.is_word:
                word_index[i] = len(word_index)
        # deny/confirm only count near the start: "No, make it large" vs "no milk".
        max_word_pos = {"cancel": None, "done": None, "deny": 1, "confirm": 2}

        def counts(start: int, limit: int | None) -> bool:
            negated = start > 0 and tokens[start - 1].text in NEGATIONS
            return not negated and (limit is None or word_index[start] <= limit)

        found = set()
        for name, phrases in self._intents.items():
            limit = max_word_pos[name]
            for phrase in phrases:
                if any(counts(s, limit) for s in _find(tokens, phrase)):
                    found.add(name)
                    break
        return found

    def extract(self, text: str) -> Extraction:
        tokens = tokenize(text)
        matches = self._menu_matches(tokens)
        covered = {i for m in matches for i in range(m.start, m.end)}
        result = Extraction(intents=self._intents_in(tokens))
        for m in matches:
            if m.category in ("drink", "off_menu"):
                prefix = self._unknown_prefix(tokens, m, covered)
                if prefix or m.category == "off_menu":
                    name = " ".join(t.text for t in tokens[m.start : m.end])
                    result.unknown_item = " ".join([*prefix, name])
                    continue
            if m.category == "extra_shots":
                result.slots["extra_shots"] = self._shot_count(tokens, m)
            elif m.category != "off_menu":
                # Later mentions win: "a latte, no, an americano".
                result.slots[m.category] = m.value
        if result.unknown_item and "drink" in result.slots:
            # A valid drink in the same sentence is a new request; keep it.
            result.unknown_item = None
        return result

    def unknown_mentions(self, text: str) -> list[str]:
        """Off-menu items mentioned in ``text``. Used by the output guard."""
        tokens = tokenize(text)
        matches = self._menu_matches(tokens)
        covered = {i for m in matches for i in range(m.start, m.end)}
        found = []
        for m in matches:
            if m.category not in ("drink", "off_menu"):
                continue
            prefix = self._unknown_prefix(tokens, m, covered)
            if prefix or m.category == "off_menu":
                found.append(" ".join([*prefix, *(t.text for t in tokens[m.start : m.end])]))
        return found
