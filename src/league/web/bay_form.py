"""Season setup's bay settings card, which the create form and the read-back both post: one
section per menu, each line of it a setting and its value (SPEC section 7).

A section is a `BayMenu` and a line a `BaySetting` as typed, whose menu is its section's name.
"""

from collections.abc import Sequence

from fastapi.datastructures import FormData

from league.domain.bay import BayMenu
from league.domain.facts import BaySetting

NEW_MENU = BayMenu("", (BaySetting("", "", ""),))


def _listed(form: FormData, name: str) -> tuple[str, ...]:
    return tuple(value if isinstance(value, str) else "" for value in form.getlist(name))


def typed_menus(form: FormData) -> tuple[BayMenu, ...]:
    """The card's sections as posted, in the order drawn: each section's `menu`, and each line's
    section in `line_menu`, with its `setting` and `value`, untrimmed."""
    names = _listed(form, "menu")
    lines: list[list[BaySetting]] = [[] for _ in names]
    posted = zip(
        _listed(form, "line_menu"), _listed(form, "setting"), _listed(form, "value"), strict=True
    )
    for section, setting, value in posted:
        menu = int(section)
        lines[menu].append(BaySetting(names[menu], setting, value))
    return tuple(BayMenu(name, tuple(held)) for name, held in zip(names, lines, strict=True))


def pressed_menus(form: FormData, menus: tuple[BayMenu, ...]) -> tuple[BayMenu, ...] | None:
    """The sections with an empty line at the end of the one Add a setting names, an unnamed
    section added after the last by Add a menu, or the line a line's Remove names, "section-line",
    taken away. None when none of those sent the form."""
    add, remove = form.get("add"), form.get("remove")
    if form.get("add_menu") is not None:
        return (*menus, NEW_MENU)
    if isinstance(add, str):
        at = int(add)
        lines = (*menus[at].lines, BaySetting(menus[at].name, "", ""))
    elif isinstance(remove, str):
        section, _, line = remove.partition("-")
        at, gone = int(section), int(line)
        lines = menus[at].lines[:gone] + menus[at].lines[gone + 1 :]
    else:
        return None
    return (*menus[:at], BayMenu(menus[at].name, lines), *menus[at + 1 :])


def typed_settings(menus: Sequence[BayMenu]) -> tuple[BaySetting, ...]:
    """The lines in section order, each field trimmed at its ends and its menu its section's
    name, with a line that has no setting and no value dropped (D18)."""
    return tuple(
        BaySetting(menu.name.strip(), line.setting.strip(), line.value.strip())
        for menu in menus
        for line in menu.lines
        if line.setting.strip() or line.value.strip()
    )
