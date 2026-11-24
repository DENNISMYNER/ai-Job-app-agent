"""Apply a field plan to a live page, then read values back to verify.

This module can navigate to the *next* page of a multi-step form, but it has NO code path
that clicks a final submit button - that lives only in ``runner.submit_application`` and
is guarded by explicit user approval.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.automation.detector import find_next_button, scan_page
from app.automation.mapper import FieldPlan

log = logging.getLogger(__name__)


def _sel(field_id: str) -> str:
    return f'[data-ja-id="{field_id}"]'


def apply_plan(page, plans: list[FieldPlan], files: dict[str, Path | None]) -> list[dict]:
    """Returns one result per field: {field_id, label, filled, verified, note}."""
    results = []
    for pl in plans:
        r = {"field_id": pl.field_id, "label": pl.label, "action": pl.action, "status": pl.status,
             "value": pl.value if pl.kind != "file" else "", "source": pl.source, "required": pl.required,
             "filled": False, "verified": False, "note": pl.reason}
        try:
            if pl.action == "fill":
                loc = page.locator(_sel(pl.field_id))
                loc.fill(pl.value)
                r["filled"], r["verified"] = True, loc.input_value() == pl.value
            elif pl.action == "select":
                loc = page.locator(_sel(pl.field_id))
                loc.select_option(label=pl.value)
                chosen = loc.evaluate("e => e.options[e.selectedIndex] ? e.options[e.selectedIndex].text.trim() : ''")
                r["filled"], r["verified"] = True, chosen == pl.value
            elif pl.action == "check" and pl.option_id:
                loc = page.locator(_sel(pl.option_id))
                loc.check()
                r["filled"], r["verified"] = True, loc.is_checked()
            elif pl.action in {"upload_cv", "upload_letter"}:
                path = files.get("cv" if pl.action == "upload_cv" else "letter")
                if path and Path(path).exists():
                    page.locator(_sel(pl.field_id)).set_input_files(str(path))
                    name = page.locator(_sel(pl.field_id)).evaluate("e => e.files && e.files[0] ? e.files[0].name : ''")
                    r["filled"], r["verified"] = True, name == Path(path).name
                else:
                    r["note"] = "File not available"
        except Exception as exc:  # noqa: BLE001 - one bad field must not abort the form
            r["note"] = f"Could not fill: {type(exc).__name__}"
            r["status"] = "needs_user"
        results.append(r)
    return results


def read_values(page) -> dict[str, dict]:
    """Current state of every visible field, keyed by id (used for deterministic validation)."""
    scan = scan_page(page)
    out = {}
    for f in scan.fields:
        if f["kind"] == "radio":
            out[f["id"]] = {"label": f["label"], "required": f["required"], "filled": bool(f["value"])}
        elif f["kind"] == "checkbox":
            out[f["id"]] = {"label": f["label"], "required": f["required"], "filled": bool(f["checked"])}
        elif f["kind"] == "file":
            n = page.locator(_sel(f["id"])).evaluate("e => e.files ? e.files.length : 0")
            out[f["id"]] = {"label": f["label"], "required": f["required"], "filled": n > 0}
        else:
            out[f["id"]] = {"label": f["label"], "required": f["required"], "filled": bool(str(f["value"]).strip())}
    return out


def missing_required(page) -> list[str]:
    return [v["label"] or k for k, v in read_values(page).items() if v["required"] and not v["filled"]]


def advance(page) -> bool:
    """Click a 'Next/Continue' button if one exists. Never clicks submit."""
    scan = scan_page(page)
    nxt = find_next_button(scan)
    if not nxt:
        return False
    page.locator(_sel(nxt["id"])).click()
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:  # noqa: BLE001 - SPA steps do not navigate
        pass
    page.wait_for_timeout(300)
    return True
