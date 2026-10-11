"""Scene Director: owns the order state and decides the NPC's next action.

The LLM never holds state. It only phrases the action chosen here, so task success is
decided deterministically and can be unit tested.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.scenes.extractor import Extraction, RuleExtractor
from app.scenes.models import Scene

TERMINAL_PHASES = ("completed", "cancelled")
SLOT_NAMES = ("drink", "size", "temperature", "milk", "extra_shots")


class InvalidTransitionError(RuntimeError):
    pass


class SessionEndedError(RuntimeError):
    pass


@dataclass
class Suggestion:
    """A value the NPC proposed; a 'yes' from the user applies it."""

    slot: str
    value: str | int | None


@dataclass
class OrderState:
    phase: str = "greeting"
    slots: dict[str, str | int | None] = field(default_factory=lambda: dict.fromkeys(SLOT_NAMES))
    user_turns: int = 0
    options_offered: bool = False
    pending: Suggestion | None = None
    user_confirmed: bool = False
    end_reason: str | None = None
    last_action: str | None = None


@dataclass(frozen=True)
class DirectorTurn:
    action: str
    phase: str
    context: dict[str, str]
    extraction: Extraction | None
    slots: dict[str, str | int | None]
    missing_required: list[str]
    ended: bool
    success: bool | None
    end_reason: str | None


def human_join(items: list[str], conj: str = "or") -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    return f"{', '.join(items[:-1])}, {conj} {items[-1]}"


class Director:
    def __init__(
        self,
        scene: Scene,
        extractor: RuleExtractor | None = None,
        assist: Callable[[str], Extraction | None] | None = None,
    ) -> None:
        self.scene = scene
        self.extractor = extractor or RuleExtractor(scene)
        # Consulted only when the rules understood nothing (e.g. "something sweet").
        self.assist = assist
        self.state = OrderState()

    # ----- public API -------------------------------------------------------------------

    def start(self) -> DirectorTurn:
        return self._turn("greet", None, {})

    def handle(self, text: str) -> DirectorTurn:
        if self.state.phase in TERMINAL_PHASES:
            raise SessionEndedError("The scene has already ended.")
        self.state.user_turns += 1
        ext = self.extractor.extract(text)
        if ext.is_empty and self.assist is not None:
            ext = self.assist(text) or ext
        action, context = self._decide(ext)
        limit = self.scene.max_user_turns
        if (
            limit
            and self.state.user_turns >= limit
            and action not in ("close", "acknowledge_cancel")
        ):
            action, context = "end_unfinished", {}
            self.state.end_reason = "max_user_turns"
        return self._turn(action, ext, context)

    def end_by_user(self) -> DirectorTurn:
        """User left the scene (e.g. closed the session) before finishing."""
        if self.state.phase not in TERMINAL_PHASES:
            self.state.end_reason = "user_ended"
            return self._turn("acknowledge_cancel", None, {})
        return self._snapshot(action="none", context={}, extraction=None)

    @property
    def missing_required(self) -> list[str]:
        return [s for s in self.scene.slots.required if self.state.slots.get(s) is None]

    # ----- decision logic ---------------------------------------------------------------

    def _decide(self, ext: Extraction) -> tuple[str, dict[str, str]]:
        s = self.state
        prior_phase = s.phase
        pending, s.pending = s.pending, None

        if "cancel" in ext.intents:
            s.end_reason = "user_cancelled"
            return "acknowledge_cancel", {}

        agreed = bool(ext.intents & {"confirm", "done"})
        if pending and agreed and pending.slot not in ext.slots:
            s.slots[pending.slot] = pending.value
        elif pending and "deny" in ext.intents and not ext.slots:
            return "ask_change", {}

        changed = self._apply(ext.slots)

        conflict = self._conflict()
        if conflict:
            return conflict
        if ext.unknown_item:
            return "handle_unavailable", {"item": ext.unknown_item}

        if prior_phase == "confirming":
            if changed:
                return "confirm_order", {}
            if agreed:
                s.user_confirmed = True
                s.end_reason = "completed"
                return "close", {}
            if "deny" in ext.intents:
                return "ask_change", {}
            return "confirm_order", {}

        missing = self.missing_required
        if missing:
            if "drink" in missing:
                nothing_understood = not changed and not (pending and agreed)
                return ("clarify" if nothing_understood else "ask_drink"), {}
            return f"ask_{missing[0]}", {}

        drink = self.scene.menu.drink(str(s.slots["drink"]))
        can_customize = drink.allows_milk or self.scene.menu.extra_shots.max > 0
        untouched = s.slots["milk"] is None and s.slots["extra_shots"] is None
        if not s.options_offered and can_customize and untouched:
            s.options_offered = True
            return "offer_options", {}
        # "Yes, sure." to "Milk or an extra shot?" says yes to something, but not to what.
        just_yes = "confirm" in ext.intents and not ({"done", "deny"} & ext.intents)
        if s.last_action == "offer_options" and just_yes and not changed:
            return "ask_which_option", {}
        return "confirm_order", {}

    def _apply(self, updates: dict[str, str | int]) -> bool:
        changed = False
        for slot, value in updates.items():
            if self.state.slots.get(slot) != value:
                self.state.slots[slot] = value
                changed = True
        drink_id = self.state.slots["drink"]
        if drink_id is not None and self.state.slots["temperature"] is None:
            temps = self.scene.menu.drink(str(drink_id)).temperatures
            if len(temps) == 1:
                self.state.slots["temperature"] = temps[0]
        return changed

    def _conflict(self) -> tuple[str, dict[str, str]] | None:
        s = self.state
        if s.slots["drink"] is None:
            return None
        drink = self.scene.menu.drink(str(s.slots["drink"]))
        temp = s.slots["temperature"]
        if temp is not None and temp not in drink.temperatures:
            s.slots["temperature"] = None
            if len(drink.temperatures) == 1:
                s.pending = Suggestion("temperature", drink.temperatures[0])
            return "handle_unsupported_temperature", {}
        milk = s.slots["milk"]
        if milk not in (None, "none") and not drink.allows_milk:
            s.slots["milk"] = None
            s.pending = Suggestion("milk", "none")
            return "handle_unsupported_milk", {}
        return None

    # ----- turn building ----------------------------------------------------------------

    def _turn(self, action: str, ext: Extraction | None, context: dict[str, str]) -> DirectorTurn:
        new_phase = self.scene.actions[action].phase
        if new_phase != self.state.phase and new_phase not in self.scene.allowed_next_phases(
            self.state.phase
        ):
            raise InvalidTransitionError(f"{self.state.phase} -> {new_phase} via '{action}'")
        self.state.phase = new_phase
        self.state.last_action = action
        return self._snapshot(action, context, ext)

    def _snapshot(
        self, action: str, context: dict[str, str], extraction: Extraction | None
    ) -> DirectorTurn:
        s = self.state
        ended = s.phase in TERMINAL_PHASES
        success = None
        if ended:
            cond = self.scene.success_condition
            success = (not cond.all_required_slots_filled or not self.missing_required) and (
                not cond.user_confirmed or s.user_confirmed
            )
            success = success and s.phase == "completed"
        return DirectorTurn(
            action=action,
            phase=s.phase,
            context={**self.template_context(), **context},
            extraction=extraction,
            slots=dict(s.slots),
            missing_required=self.missing_required,
            ended=ended,
            success=success,
            end_reason=s.end_reason,
        )

    def template_context(self) -> dict[str, str]:
        menu = self.scene.menu
        s = self.state
        drink = menu.drink(str(s.slots["drink"])) if s.slots["drink"] else None
        return {
            "menu_list": human_join([d.name for d in menu.drinks]),
            "sizes": human_join([o.id for o in menu.sizes]),
            "order_summary": self.order_summary(),
            "drink_name": drink.name if drink else "drink",
            "allowed_temperatures": human_join(drink.temperatures) if drink else "",
            "item": "",
        }

    def order_summary(self) -> str:
        s = self.state.slots
        if not s["drink"]:
            return "your order"
        drink = self.scene.menu.drink(str(s["drink"]))
        words = [str(s["size"] or "")]
        if s["temperature"] and len(drink.temperatures) > 1:
            words.append(str(s["temperature"]))
        words.append(drink.name)
        phrase = " ".join(w for w in words if w)
        article = "an" if phrase[0].lower() in "aeiou" else "a"
        extras = []
        if s["milk"] and s["milk"] != "none":
            extras.append(f"{s['milk']} milk")
        if s["extra_shots"]:
            n = int(s["extra_shots"])
            extras.append(f"{'an' if n == 1 else n} extra shot{'s' if n > 1 else ''}")
        return f"{article} {phrase}" + (f" with {human_join(extras, 'and')}" if extras else "")
