"""No-color palette uses terminal defaults for every color-bearing role."""

from amberclaw.tui.themes.no_color import NoColorTheme


def test_no_color_palette_does_not_inherit_colored_roles():
    roles = NoColorTheme.model_dump(exclude={"name"})
    assert all(value in {"default", "dim", "bold"} for value in roles.values())
    assert NoColorTheme.error == "bold"
