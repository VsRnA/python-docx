from pathlib import Path
import unittest


THEME_CSS = (
    Path(__file__).resolve().parents[1]
    / "themes"
    / "villartec-manual-a4"
    / "1.0"
    / "print.css"
)


class A4ThemePaginationTests(unittest.TestCase):
    def test_content_reflows_without_model_estimated_forced_breaks(self) -> None:
        css = THEME_CSS.read_text(encoding="utf-8")

        self.assertIn(".manual-section { break-inside: auto; }", css)
        self.assertIn(".manual-page-break { display: none; }", css)
        self.assertNotIn(".manual-section { break-before: page; }", css)
        self.assertNotIn("break-after: page", css)

    def test_running_header_uses_fixed_position_for_table_continuations(self) -> None:
        css = THEME_CSS.read_text(encoding="utf-8")

        self.assertIn("position: fixed;", css)
        self.assertNotIn("position: running(manualHeader);", css)


if __name__ == "__main__":
    unittest.main()
