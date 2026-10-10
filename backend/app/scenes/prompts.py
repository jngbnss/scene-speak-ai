"""Prompt builders. The LLM only sees the scene facts and the Director's chosen action."""

from app.ai.types import ChatMessage
from app.scenes.director import DirectorTurn, human_join
from app.scenes.models import Scene

HISTORY_TURNS = 8


def _menu_facts(scene: Scene) -> str:
    menu = scene.menu
    drinks = "; ".join(
        f"{d.name} ({'/'.join(d.temperatures)}, {'milk ok' if d.allows_milk else 'no milk'})"
        for d in menu.drinks
    )
    milks = human_join([m.id for m in menu.milks if m.id != "none"])
    sizes = human_join([s.id for s in menu.sizes])
    return (
        f"Drinks: {drinks}.\nSizes: {sizes}.\nMilk: {milks}.\n"
        f"Extra espresso shots: up to {menu.extra_shots.max}."
    )


def npc_messages(
    scene: Scene, turn: DirectorTurn, history: list[tuple[str, str]]
) -> list[ChatMessage]:
    npc = scene.npc
    instruction = scene.actions[turn.action].instruction.format_map(turn.context)
    order = turn.context["order_summary"] if turn.slots.get("drink") else "nothing yet"
    forbidden = "\n".join(f"- {f}" for f in npc.forbidden)
    system = f"""You are the {npc.role} at a {scene.setting.place}. {npc.persona}
{scene.setting.description_for_llm.strip()}
The customer is a {scene.user_role} practicing English.

Menu (the only things that exist):
{_menu_facts(scene)}

Rules:
- Speak only as the barista, in natural spoken English.
- At most {npc.max_reply_sentences} short sentences and under 25 words in total.
  Count your sentences.
- Do exactly the task below and nothing else. Do not ask about anything the task does not mention.
- Never mention prices.
{forbidden}

Current order: {order}
Your task now: {instruction}

Return JSON: {{"reply": "<what you say>"}}"""
    messages = [ChatMessage(role="system", content=system)]
    for speaker, text in history[-HISTORY_TURNS:]:
        messages.append(
            ChatMessage(role="user" if speaker == "user" else "assistant", content=text)
        )
    if not history or history[-1][0] != "user":
        messages.append(ChatMessage(role="user", content="(The customer is at the counter.)"))
    return messages


def extraction_messages(scene: Scene, text: str) -> list[ChatMessage]:
    drinks = human_join([d.name for d in scene.menu.drinks])
    system = f"""You read what a café customer said and extract their order.
Menu drinks: {drinks}. Sizes: {human_join([s.id for s in scene.menu.sizes])}.
Temperatures: hot, iced. Milk: {human_join([m.id for m in scene.menu.milks if m.id != "none"])}.

Rules:
- Fill a field only if the customer explicitly said it. Otherwise null.
- If the customer asked for a food or drink that is not on the menu, put its name
  in requested_item_not_on_menu.
- intent is one of: order, modify, confirm, deny, cancel, question, other."""
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=f"Customer: {text}"),
    ]
