from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Setting(_Strict):
    place: str
    time: str
    description_for_llm: str


class Npc(_Strict):
    id: str
    role: str
    persona: str
    voice: str
    max_reply_sentences: int
    forbidden: list[str]


class Goal(_Strict):
    id: str
    description_ko: str


class Drink(_Strict):
    id: str
    name: str
    aliases: list[str]
    temperatures: list[str]
    allows_milk: bool


class Option(_Strict):
    id: str
    aliases: list[str]


class ExtraShots(_Strict):
    min: int
    max: int
    aliases: list[str]


class Menu(_Strict):
    drinks: list[Drink]
    sizes: list[Option]
    temperatures: list[Option]
    milks: list[Option]
    extra_shots: ExtraShots

    def drink(self, drink_id: str) -> Drink:
        return next(d for d in self.drinks if d.id == drink_id)


class Intents(_Strict):
    cancel: list[str]
    done: list[str]
    deny: list[str]
    confirm: list[str]


class Slots(_Strict):
    required: list[str]
    optional: list[str]


class Phase(_Strict):
    id: str
    next: list[str]


class Action(_Strict):
    phase: str
    instruction: str
    fallback: str


class Guard(_Strict):
    forbidden_patterns: list[str]


class SuccessCondition(_Strict):
    all_required_slots_filled: bool
    user_confirmed: bool


class EndCondition(_Strict):
    phase: str | None = None
    max_user_turns: int | None = None


class Learning(_Strict):
    target_expressions: list[str]
    feedback_focus: list[str]


class Scene(_Strict):
    id: str
    version: int
    locale: str
    title: str
    setting: Setting
    npc: Npc
    user_role: str
    goal: Goal
    menu: Menu
    off_menu_terms: list[str]
    intents: Intents
    slots: Slots
    phases: list[Phase]
    actions: dict[str, Action]
    guard: Guard
    success_condition: SuccessCondition
    end_conditions: list[EndCondition]
    learning: Learning

    @property
    def max_user_turns(self) -> int | None:
        return next((c.max_user_turns for c in self.end_conditions if c.max_user_turns), None)

    @property
    def hotwords(self) -> list[str]:
        """Menu words that help the speech recognizer (EXP-ASR-001)."""
        words = [d.name for d in self.menu.drinks]
        words += [a for m in self.menu.milks for a in m.aliases if " " in a and m.id != "none"]
        return list(dict.fromkeys(words))

    def allowed_next_phases(self, phase_id: str) -> list[str]:
        return next(p.next for p in self.phases if p.id == phase_id)
