"""The operator's view of a shift.

An airport does not buy a robot. It buys a service level it can evidence, so the
question that decides a pilot is not "does the chair work" but "how would I run
thirty of these and prove they met their obligations". This renders the answer
from a completed run: how long people waited, how the fleet spent its time, and
how often a human had to be called.

The timeline is coloured by how usefully each chair is spending its time —
darkest for carrying a passenger, lightest for sitting available, with stopped
called out separately. An operator reads utilisation off it without a legend
lookup: more dark is better.

    from saarthi.dashboard import render_dashboard
    render_dashboard(fleet, "shift.html", title="Morning shift")
"""

from __future__ import annotations

import html
import pathlib
from dataclasses import dataclass

from .fleet import ChairState, Fleet

#: How each chair state is counted. Ordered best use of a chair to worst.
BANDS: list[tuple[str, str, frozenset[ChairState]]] = [
    (
        "carrying",
        "Carrying a passenger",
        frozenset(
            {
                ChairState.BOARDING,
                ChairState.CARRYING,
                ChairState.ALIGHTING,
                ChairState.AWAITING_DESTINATION,
            }
        ),
    ),
    (
        "moving",
        "Repositioning empty",
        frozenset({ChairState.TO_PICKUP, ChairState.RETURNING, ChairState.STAGING}),
    ),
    ("available", "Available", frozenset({ChairState.IDLE, ChairState.CHARGING})),
    ("stopped", "Stopped", frozenset({ChairState.BLOCKED, ChairState.ESTOP})),
]

_BAND_OF: dict[ChairState, str] = {
    state: key for key, _, states in BANDS for state in states
}


@dataclass(frozen=True)
class Span:
    chair: str
    band: str
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def spans(fleet: Fleet) -> list[Span]:
    """Turn the state-change log into intervals, one per chair per band run."""
    if not fleet.history:
        return []

    out: list[Span] = []
    for chair_id in fleet.chairs:
        changes = [(t, state) for t, cid, state in fleet.history if cid == chair_id]
        if not changes:
            continue
        for index, (start, state) in enumerate(changes):
            end = changes[index + 1][0] if index + 1 < len(changes) else fleet.now
            if end <= start:
                continue
            band = _BAND_OF.get(state)
            if band is None:
                continue
            # Merge with the previous span when the band has not actually changed:
            # idle -> charging is two states but one thing to look at.
            if out and out[-1].chair == chair_id and out[-1].band == band:
                merged = out.pop()
                out.append(Span(chair_id, band, merged.start_s, end))
            else:
                out.append(Span(chair_id, band, start, end))
    return out


def utilisation(fleet: Fleet) -> dict[str, float]:
    """Share of fleet time spent in each band."""
    totals: dict[str, float] = {key: 0.0 for key, _, _ in BANDS}
    for span in spans(fleet):
        totals[span.band] += span.duration_s
    grand = sum(totals.values())
    if grand == 0:
        return totals
    return {key: value / grand for key, value in totals.items()}


def _mmss(seconds: float) -> str:
    """Minutes and seconds, for the durations an operator compares."""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


def _elapsed(seconds: float) -> str:
    """A whole shift reads better in hours than as a large minute count."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def _esc(value: object) -> str:
    return html.escape(str(value))


_STYLE = """
:root {
  color-scheme: light;
  --surface:        #fcfcfb;
  --panel:          #ffffff;
  --rule:           #e4e3df;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #76756f;
  --carrying:       #1c5cab;
  --moving:         #3987e5;
  --available:      #86b6ef;
  --stopped:        #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface:        #1a1a19;
    --panel:          #232322;
    --rule:           #383835;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #94938a;
    --carrying:       #9ec5f4;
    --moving:         #5598e7;
    --available:      #184f95;
    --stopped:        #d03b3b;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface:        #1a1a19;
  --panel:          #232322;
  --rule:           #383835;
  --text-primary:   #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted:     #94938a;
  --carrying:       #9ec5f4;
  --moving:         #5598e7;
  --available:      #184f95;
  --stopped:        #d03b3b;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--surface);
  color: var(--text-primary);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-text-size-adjust: 100%;
}
.wrap { max-width: 1040px; margin: 0 auto; padding: 32px 16px 64px; }
header { margin-bottom: 28px; }
h1 { font-size: 24px; font-weight: 650; margin: 0 0 4px; letter-spacing: -0.01em; }
.sub { color: var(--text-secondary); font-size: 14px; margin: 0; }
h2 {
  font-size: 13px; font-weight: 650; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-secondary);
  margin: 36px 0 12px;
}
.card {
  background: var(--panel); border: 1px solid var(--rule);
  border-radius: 10px; padding: 18px;
}

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.kpi { background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; padding: 14px 16px; }
.kpi .value { font-size: 30px; font-weight: 640; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.kpi .label { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.kpi .note { font-size: 12px; color: var(--text-muted); margin-top: 6px; }

.legend { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 14px; }
.legend span { display: flex; align-items: center; gap: 7px; font-size: 13px; color: var(--text-secondary); }
.swatch { width: 14px; height: 14px; border-radius: 3px; flex: none; }
.swatch.carrying  { background: var(--carrying); }
.swatch.moving    { background: var(--moving); }
.swatch.available { background: var(--available); }
.swatch.stopped {
  background: var(--stopped);
  background-image: repeating-linear-gradient(45deg,
    rgba(255,255,255,.55) 0 2px, transparent 2px 5px);
}

.rows { display: grid; gap: 8px; }
.row { display: grid; grid-template-columns: 76px 1fr; align-items: center; gap: 12px; }
.row .name { font-size: 13px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.track { position: relative; height: 22px; background: var(--surface); border-radius: 4px; }
.seg {
  position: absolute; top: 0; bottom: 0;
  border-right: 2px solid var(--panel);
  min-width: 2px;
}
.seg:first-of-type { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }
.seg:last-of-type { border-right: 0; border-top-right-radius: 4px; border-bottom-right-radius: 4px; }
.seg.carrying  { background: var(--carrying); }
.seg.moving    { background: var(--moving); }
.seg.available { background: var(--available); }
.seg.stopped {
  background: var(--stopped);
  background-image: repeating-linear-gradient(45deg,
    rgba(255,255,255,.55) 0 2px, transparent 2px 5px);
}
.axis {
  display: grid; grid-template-columns: 76px 1fr; gap: 12px;
  margin-top: 8px; font-size: 12px; color: var(--text-muted);
}
.ticks { display: flex; justify-content: space-between; font-variant-numeric: tabular-nums; }

.bars { display: grid; gap: 10px; }
.bar-row { display: grid; grid-template-columns: 150px 1fr 62px; align-items: center; gap: 12px; font-size: 13px; }
.bar-row .who { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { background: var(--surface); border-radius: 4px; height: 18px; }
.bar { height: 18px; background: var(--carrying); border-radius: 0 4px 4px 0; min-width: 3px; }
.bar-row .num { text-align: right; color: var(--text-secondary); font-variant-numeric: tabular-nums; }

.scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 520px; }
th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--rule); }
th { font-weight: 600; color: var(--text-secondary); font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:last-child td { border-bottom: 0; }

[data-tip] { cursor: default; }
#tip {
  position: fixed; pointer-events: none; opacity: 0; transition: opacity .1s;
  background: var(--text-primary); color: var(--surface);
  padding: 6px 9px; border-radius: 6px; font-size: 12px; white-space: nowrap; z-index: 9;
}
footer { margin-top: 40px; color: var(--text-muted); font-size: 12px; }
@media (max-width: 560px) {
  .wrap { padding: 24px 16px 48px; }
  .row { grid-template-columns: 52px 1fr; gap: 8px; }
  .axis { grid-template-columns: 52px 1fr; gap: 8px; }
  .ticks span:nth-child(even) { display: none; }
  .bar-row { grid-template-columns: 88px 1fr 48px; gap: 8px; }
  .card { padding: 14px; }
  .kpi .value { font-size: 26px; }
}
"""

_SCRIPT = """
const tip = document.getElementById('tip');
addEventListener('pointerover', e => {
  const el = e.target.closest('[data-tip]');
  if (!el) return;
  tip.textContent = el.dataset.tip;
  tip.style.opacity = '1';
});
addEventListener('pointermove', e => {
  if (tip.style.opacity !== '1') return;
  const pad = 14;
  let x = e.clientX + pad, y = e.clientY + pad;
  const r = tip.getBoundingClientRect();
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - pad;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - pad;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
});
addEventListener('pointerout', e => {
  if (e.target.closest('[data-tip]')) tip.style.opacity = '0';
});
"""


def _kpis(fleet: Fleet) -> str:
    summary = fleet.summary()
    used = utilisation(fleet)
    carrying = used.get("carrying", 0.0)

    escalations = int(summary["escalations"])
    cards = [
        (
            f"{int(summary['delivered'])}/{int(summary['requests'])}",
            "Journeys completed",
            f"{int(summary['outstanding'])} still outstanding",
        ),
        (
            _mmss(summary["mean_wait_s"]),
            "Mean wait for a chair",
            "from asking to being collected",
        ),
        (_mmss(summary["worst_wait_s"]), "Worst wait", "the number an SLA is written against"),
        (
            f"{carrying:.0%}",
            "Fleet time carrying",
            f"{used.get('moving', 0.0):.0%} repositioning empty",
        ),
        (
            str(escalations),
            "Attendant call-outs",
            "a chair that could not resolve it alone"
            if escalations
            else "no chair needed a human",
        ),
    ]
    return "\n".join(
        f'<div class="kpi"><div class="value">{_esc(v)}</div>'
        f'<div class="label">{_esc(label)}</div>'
        f'<div class="note">{_esc(note)}</div></div>'
        for v, label, note in cards
    )


def _timeline(fleet: Fleet) -> str:
    all_spans = spans(fleet)
    if not all_spans or fleet.now <= 0:
        return '<p class="sub">No shift recorded.</p>'

    labels = {key: label for key, label, _ in BANDS}
    rows = []
    for chair_id in fleet.chairs:
        segments = [s for s in all_spans if s.chair == chair_id]
        pieces = []
        for span in segments:
            left = span.start_s / fleet.now * 100
            width = max(span.duration_s / fleet.now * 100, 0.25)
            tip = (
                f"{chair_id} · {labels[span.band]} · "
                f"{_mmss(span.start_s)}–{_mmss(span.end_s)} ({_mmss(span.duration_s)})"
            )
            pieces.append(
                f'<div class="seg {span.band}" style="left:{left:.3f}%;width:{width:.3f}%" '
                f'data-tip="{_esc(tip)}"></div>'
            )
        rows.append(
            f'<div class="row"><div class="name">{_esc(chair_id)}</div>'
            f'<div class="track">{"".join(pieces)}</div></div>'
        )

    ticks = "".join(
        f"<span>{_mmss(fleet.now * fraction / 4)}</span>" for fraction in range(5)
    )
    legend = "".join(
        f'<span><i class="swatch {key}"></i>{_esc(label)}</span>' for key, label, _ in BANDS
    )
    return (
        f'<div class="legend">{legend}</div>'
        f'<div class="rows">{"".join(rows)}</div>'
        f'<div class="axis"><div></div><div class="ticks">{ticks}</div></div>'
    )


def _waits(fleet: Fleet) -> str:
    done = [r for r in fleet.requests if r.delivered_s is not None]
    if not done:
        return '<p class="sub">No journeys completed.</p>'

    worst = max(r.wait_time_s(fleet.now) for r in done) or 1.0
    rows = []
    for request in done:
        wait = request.wait_time_s(fleet.now)
        width = max(wait / worst * 100, 1.0)
        tip = f"{request.passenger} waited {_mmss(wait)} for {request.assigned_to}"
        rows.append(
            f'<div class="bar-row"><div class="who">{_esc(request.passenger)}</div>'
            f'<div class="bar-track"><div class="bar" style="width:{width:.2f}%" '
            f'data-tip="{_esc(tip)}"></div></div>'
            f'<div class="num">{_mmss(wait)}</div></div>'
        )
    return f'<div class="bars">{"".join(rows)}</div>'


def _journeys_table(fleet: Fleet) -> str:
    rows = []
    for request in fleet.requests:
        delivered = _mmss(request.delivered_s) if request.delivered_s is not None else "—"
        wait = (
            _mmss(request.wait_time_s(fleet.now))
            if request.picked_up_s is not None
            else "waiting"
        )
        origin = "call button" if request.from_call_point else (request.flight or "—")
        rows.append(
            "<tr>"
            f"<td>{_esc(request.id)}</td>"
            f"<td>{_esc(request.passenger)}</td>"
            f"<td>{_esc(origin)}</td>"
            f"<td>{_esc(request.pickup)} &rarr; {_esc(request.gate or '—')}</td>"
            f"<td>{_esc(request.assigned_to or '—')}</td>"
            f'<td class="num">{_esc(wait)}</td>'
            f'<td class="num">{_esc(delivered)}</td>'
            "</tr>"
        )
    return (
        '<div class="scroll">'
        "<table><thead><tr><th>Ref</th><th>Passenger</th><th>Flight</th>"
        "<th>Journey</th><th>Chair</th><th class='num'>Waited</th>"
        "<th class='num'>Delivered</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _chairs_table(fleet: Fleet) -> str:
    """The timeline's table counterpart, so the chart is never the only way in."""
    by_chair: dict[str, dict[str, float]] = {
        cid: {key: 0.0 for key, _, _ in BANDS} for cid in fleet.chairs
    }
    for span in spans(fleet):
        by_chair[span.chair][span.band] += span.duration_s

    rows = []
    for chair_id, chair in fleet.chairs.items():
        totals = by_chair[chair_id]
        grand = sum(totals.values()) or 1.0
        cells = "".join(
            f'<td class="num">{totals[key] / grand:.0%}</td>' for key, _, _ in BANDS
        )
        rows.append(
            f"<tr><td>{_esc(chair_id)}</td>{cells}"
            f'<td class="num">{chair.battery_fraction:.0%}</td>'
            f"<td>{_esc(chair.node)}</td></tr>"
        )
    heads = "".join(f"<th class='num'>{_esc(label)}</th>" for _, label, _ in BANDS)
    return (
        '<div class="scroll">'
        f"<table><thead><tr><th>Chair</th>{heads}"
        "<th class='num'>Battery</th><th>Now at</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render(fleet: Fleet, *, title: str = "Shift report") -> str:
    """Build the dashboard HTML for a completed run."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>{_esc(title)}</h1>
  <p class="sub">{_esc(fleet.tmap.name)} &middot; {len(fleet.chairs)} chairs &middot;
     {_elapsed(fleet.now)} elapsed</p>
</header>

<div class="kpis">{_kpis(fleet)}</div>

<h2>How the fleet spent the shift</h2>
<div class="card">{_timeline(fleet)}</div>

<h2>What each passenger waited</h2>
<div class="card">{_waits(fleet)}</div>

<h2>Chairs</h2>
<div class="card">{_chairs_table(fleet)}</div>

<h2>Journeys</h2>
<div class="card">{_journeys_table(fleet)}</div>

<footer>
  Generated from a simulated shift. Wait is measured from the passenger asking
  to the chair reaching them — the number an airport is held to.
</footer>
</div>
<div id="tip"></div>
<script>{_SCRIPT}</script>
</body>
</html>
"""


def render_dashboard(fleet: Fleet, path: str | pathlib.Path, *, title: str = "Shift report") -> pathlib.Path:
    """Render and write the dashboard. Returns the path written."""
    out = pathlib.Path(path)
    out.write_text(render(fleet, title=title), encoding="utf-8")
    return out
