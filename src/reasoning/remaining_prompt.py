_HEADER = "Roadmap tasks still open as this report's window closes:\n"
_TASK_TEMPLATE = "- {task}"

_INSTRUCTION_TEMPLATE = (
    "\n\nWrite grounded prose framing these still-open tasks for readers — "
    "what remains ahead, without inventing status beyond what is listed "
    "above — in {lang}."
)


class RemainingPromptBuilder:
    """Owns the prose-framing prompt text for `RemainingSection`: given the
    roadmap tasks still open at a report window's end, frames them for
    readers as "what remains".

    This is the residual framing primitive the narration split permits — it
    lives only for `RemainingSection`, not as a second `Reasoner`-narration
    sibling, and encapsulates its prompt string the same way
    `NarrationPromptBuilder` and `ReasoningPromptBuilder` do.
    """

    def build(self, tasks: list[str], lang: str = "ru") -> str:
        rendered_tasks = "\n".join(_TASK_TEMPLATE.format(task=task) for task in tasks)
        return f"{_HEADER}{rendered_tasks}{_INSTRUCTION_TEMPLATE.format(lang=lang)}"
