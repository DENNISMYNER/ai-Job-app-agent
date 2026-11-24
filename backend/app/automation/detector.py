"""Reusable, site-agnostic form detection.

A single in-page script walks the live DOM (not site-specific selectors) and returns every
visible input with its best-guess label, requirement flag and options. Elements are tagged
with ``data-ja-id`` so the filler can address exactly the element that was detected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

DETECT_JS = r"""
() => {
  const clean = t => (t || '').replace(/\s+/g, ' ').replace(/\*/g, '').trim();
  const visible = el => {
    if (el.type === 'file') return true;           // file inputs are often visually hidden
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.visibility !== 'hidden' && s.display !== 'none' && (r.width > 0 || r.height > 0);
  };
  const textOfLabelFor = el => {
    const out = [];
    if (el.id) { const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]'); if (l) out.push(l.innerText); }
    const wrap = el.closest('label'); if (wrap) out.push(wrap.innerText);
    const by = el.getAttribute('aria-labelledby');
    if (by) by.split(/\s+/).forEach(i => { const n = document.getElementById(i); if (n) out.push(n.innerText); });
    if (el.getAttribute('aria-label')) out.push(el.getAttribute('aria-label'));
    return out.map(clean).filter(Boolean);
  };
  const isRequired = (el, label) => el.required || el.getAttribute('aria-required') === 'true' ||
      /\*/.test((el.id && (document.querySelector('label[for="' + CSS.escape(el.id) + '"]') || {}).innerText) || '') ||
      /\*\s*$/.test((el.closest('label') || {}).innerText || '');
  const groupLabel = el => {
    const fs = el.closest('fieldset'); if (fs) { const lg = fs.querySelector('legend'); if (lg) return clean(lg.innerText); }
    const rg = el.closest('[role=radiogroup],[role=group]');
    if (rg) { const by = rg.getAttribute('aria-labelledby'); if (by) { const n = document.getElementById(by); if (n) return clean(n.innerText); }
              if (rg.getAttribute('aria-label')) return clean(rg.getAttribute('aria-label')); }
    return '';
  };
  let n = window.__ja_n || 0;   // page-global counter: ids must stay unique across multi-step scans
  const fields = [], radios = {};
  document.querySelectorAll('input, select, textarea').forEach(el => {
    const type = (el.type || el.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'image', 'reset'].includes(type)) return;
    if (!visible(el) || el.disabled) return;
    const id = el.getAttribute('data-ja-id') || ('f' + (++n));
    el.setAttribute('data-ja-id', id);
    const labels = textOfLabelFor(el);
    if (type === 'radio') {
      const key = el.name || id;
      const g = radios[key] || (radios[key] = { id: 'g:' + key, kind: 'radio', name: el.name, label: groupLabel(el), required: false, options: [], value: '' });
      g.options.push({ id, label: labels[0] || el.value, value: el.value });
      g.required = g.required || isRequired(el);
      if (el.checked) g.value = el.value;
      return;
    }
    const f = {
      id, kind: type === 'select-one' || type === 'select-multiple' ? 'select' : el.tagName.toLowerCase() === 'textarea' ? 'textarea' : type,
      name: el.name || '', label: labels[0] || '', placeholder: el.placeholder || '',
      required: isRequired(el), options: [], value: el.value || '', accept: el.accept || '', checked: !!el.checked,
    };
    if (f.kind === 'select') f.options = [...el.options].map(o => ({ label: clean(o.text), value: o.value })).filter(o => o.value !== '' || o.label);
    if (type === 'checkbox') f.value = el.checked ? 'on' : '';
    if (!f.label) {   // fall back to nearest preceding text
      let p = el.previousElementSibling; while (p && !clean(p.innerText)) p = p.previousElementSibling;
      f.label = p ? clean(p.innerText).slice(0, 200) : '';
    }
    fields.push(f);
  });
  Object.values(radios).forEach(g => fields.push(g));
  const buttons = [];
  document.querySelectorAll('button, input[type=submit], input[type=button], a[role=button]').forEach(b => {
    if (!visible(b) || b.disabled) return;
    const id = b.getAttribute('data-ja-id') || ('b' + (++n)); b.setAttribute('data-ja-id', id);
    buttons.push({ id, text: clean(b.innerText || b.value || b.getAttribute('aria-label')), type: (b.type || '').toLowerCase() });
  });
  window.__ja_n = n;
  const body = (document.body.innerText || '').toLowerCase();
  const html = document.documentElement.innerHTML.toLowerCase();
  const pw = [...document.querySelectorAll('input[type=password]')].some(visible);
  const captcha = !!document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="turnstile"], .g-recaptcha, .h-captcha, .cf-turnstile, [data-sitekey]')
      || /verify (that )?you are (a )?human|are you a robot|captcha/.test(body);
  const mfa = /(verification|security|one[- ]time|authentication) code|two[- ]factor|2fa|enter the code we sent/.test(body);
  return { url: location.href, title: document.title, fields, buttons, captcha, mfa, login: pw, text: body.slice(0, 4000), hasForm: !!document.querySelector('form') };
}
"""


@dataclass
class PageScan:
    url: str
    title: str
    fields: list[dict]
    buttons: list[dict]
    captcha: bool
    mfa: bool
    login: bool
    text: str
    has_form: bool

    @property
    def blocking(self) -> str | None:
        """Reason the agent must hand control to the user (we never bypass these)."""
        if self.captcha:
            return "A CAPTCHA / bot check is present. Please complete it yourself in the browser window."
        if self.mfa:
            return "The site is asking for a verification (MFA) code. Please enter it yourself."
        if self.login and len([f for f in self.fields if f["kind"] not in {"password", "checkbox"}]) <= 2:
            return "The site requires you to sign in. Please sign in in the browser window (the session is remembered)."
        return None


NEXT_RE = re.compile(r"^(next|continue|save (and|&) continue|proceed|next step|go to next)\b", re.I)
SUBMIT_RE = re.compile(r"\b(submit|send application|apply now|finish|complete application|submit application|apply)\b", re.I)
REVIEW_RE = re.compile(r"\b(review)\b", re.I)


def scan_page(page) -> PageScan:
    d = page.evaluate(DETECT_JS)
    return PageScan(d["url"], d["title"], d["fields"], d["buttons"], d["captcha"], d["mfa"], d["login"], d["text"], d["hasForm"])


def find_next_button(scan: PageScan) -> dict | None:
    for b in scan.buttons:
        if NEXT_RE.search(b["text"]):
            return b
    return None


def find_submit_button(scan: PageScan) -> dict | None:
    """The FINAL submit control. Deliberately never matched as a 'next' button."""
    for b in scan.buttons:
        if NEXT_RE.search(b["text"]):
            continue
        if SUBMIT_RE.search(b["text"]) or b["type"] == "submit":
            return b
    return None


def find_apply_entry(scan: PageScan) -> dict | None:
    """On a job description page without a form: the 'Apply' entry button/link (not a submit)."""
    for b in scan.buttons:
        if re.fullmatch(r"(apply( now| for this job| for this position)?|start application)", b["text"].strip(), re.I):
            return b
    return None
