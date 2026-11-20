"""Build the report slides (Asg2_315551818.pptx) on the course template.

Numbers are read from reports/validation_results.json, reports/report_data.json and
reports/weekly_capture.csv (written by main.py and scripts/report_data.py).

Usage: python slides/build_slides.py   (needs python-pptx)
"""
import copy
import csv
import json
from datetime import datetime
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
OUT = ROOT / "slides" / "Asg2_315551818.pptx"
REPO_URL = "https://github.com/malocs15/BigData2026-Assignment2"

INDIGO = RGBColor(0x34, 0x43, 0x94)      # template colour
INDIGO_LT = RGBColor(0xE6, 0xE9, 0xF6)
ORANGE = RGBColor(0xE0, 0x7A, 0x1F)
ORANGE_LT = RGBColor(0xFC, 0xEB, 0xDB)
GREEN = RGBColor(0x2E, 0x7D, 0x4F)
GREEN_LT = RGBColor(0xE1, 0xF2, 0xE7)
GREY = RGBColor(0x6B, 0x72, 0x80)
GREY_LT = RGBColor(0xF1, 0xF2, 0xF4)
DARK = RGBColor(0x1F, 0x23, 0x3A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Arial"

ACTS = ["open_pr", "open_issue", "issue_comment", "pr_review", "pr_review_comment", "push"]

val = json.loads((REPORTS / "validation_results.json").read_text())
rep = json.loads((REPORTS / "report_data.json").read_text())
weekly = list(csv.DictReader(open(REPORTS / "weekly_capture.csv")))
M = val["mean"]
S = {k: v["score"] * 100 for k, v in M.items()}
FINAL = "LightGBM (final)"
COPY = "Copy last week"
DATA_END = datetime.fromisoformat(rep["data_end"])


# --------------------------------------------------------------------------- helpers
def fmt(x):
    return f"{x:.2f}"


def text(slide, x, y, w, h, paras, size=12, color=DARK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, space_after=3, name=None):
    """paras: list of str | list of runs [(text, {opts})] | dict(runs=..., bullet=True, size=..)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, p in enumerate(paras):
        if isinstance(p, str):
            p = {"runs": [(p, {})]}
        elif isinstance(p, list):
            p = {"runs": p}
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = p.get("align", align)
        para.space_after = Pt(p.get("space_after", space_after))
        if p.get("bullet"):
            pPr = para._p.get_or_add_pPr()
            lvl = p.get("level", 0)
            pPr.set("marL", str(int(Inches(0.18 + 0.18 * lvl))))
            pPr.set("indent", str(int(-Inches(0.15))))
            for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
                for el in pPr.findall(qn(tag)):
                    pPr.remove(el)
            bu = etree.SubElement(pPr, qn("a:buChar"))
            bu.set("char", "•")
        for t, o in p["runs"]:
            r = para.add_run()
            r.text = t
            f = r.font
            f.name = o.get("font", FONT)
            f.size = Pt(o.get("size", p.get("size", size)))
            f.bold = o.get("bold", p.get("bold", bold))
            f.italic = o.get("italic", False)
            f.color.rgb = o.get("color", p.get("color", color))
            if o.get("link"):
                r.hyperlink.address = o["link"]
    return tb


def box(slide, x, y, w, h, fill=GREY_LT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08,
        dash=False, line_w=1.0):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
        if dash:
            s.line.dash_style = 4  # dash
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    s.text_frame.text = ""
    return s


def box_text(shape, paras, size=11, color=DARK, bold=False, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
             margin=0.06):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = anchor
    for i, p in enumerate(paras):
        if isinstance(p, str):
            p = [(p, {})]
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        for t, o in p:
            r = para.add_run()
            r.text = t
            r.font.name = FONT
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.italic = o.get("italic", False)
            r.font.color.rgb = o.get("color", color)
    return shape


def _arrowify(line_el, head=True, dash=False):
    ln = line_el
    if dash:
        d = etree.SubElement(ln, qn("a:prstDash"))
        d.set("val", "dash")
    if head:
        t = etree.SubElement(ln, qn("a:tailEnd"))
        t.set("type", "triangle")
        t.set("w", "med")
        t.set("h", "med")


def arrow(slide, x1, y1, x2, y2, color=INDIGO, width=1.25, head=True, dash=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    _arrowify(c.line._get_or_add_ln(), head, dash)
    return c


def polyline(slide, pts, color=INDIGO, width=1.25, head=True, dash=False):
    fb = slide.shapes.build_freeform(Inches(pts[0][0]), Inches(pts[0][1]), scale=1.0)
    fb.add_line_segments([(Inches(x), Inches(y)) for x, y in pts[1:]], close=False)
    s = fb.convert_to_shape()
    s.fill.background()
    s.line.color.rgb = color
    s.line.width = Pt(width)
    _arrowify(s.line._get_or_add_ln(), head, dash)
    return s


def style_chart(chart, size=10):
    chart.font.name = FONT
    chart.font.size = Pt(size)
    chart.font.color.rgb = DARK


def bar_chart(slide, x, y, w, h, cats, series, colors, horizontal=True, vmin=None, vmax=None, labels=True,
              legend=False, gap=60, number_format="0.0", point_colors=None, size=10):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    style_chart(ch, size)
    plot = ch.plots[0]
    plot.gap_width = gap
    plot.overlap = 0 if len(series) == 1 else -10
    for s, col in zip(plot.series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = col
        s.invert_if_negative = False
    if point_colors:
        for i, col in enumerate(point_colors):
            pt = plot.series[0].points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = col
    if labels:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format = number_format
        dl.number_format_is_linked = False
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        dl.font.size = Pt(size - 1)
        dl.font.color.rgb = DARK
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE2, 0xE4, 0xEA)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(size - 1)
    va.tick_labels.font.color.rgb = GREY
    if vmin is not None:
        va.minimum_scale = vmin
    if vmax is not None:
        va.maximum_scale = vmax
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(size)
    ca.format.line.color.rgb = RGBColor(0xC8, 0xCB, 0xD3)
    ca.has_major_gridlines = False
    if horizontal:
        ca.reverse_order = True
        va.tick_label_position  # keep default
    ch.has_title = False
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(size)
    return ch


def line_chart(slide, x, y, w, h, cats, series, colors, size=10, vmin=None, vmax=None, title=None):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    style_chart(ch, size)
    for s, col in zip(ch.plots[0].series, colors):
        s.format.line.color.rgb = col
        s.format.line.width = Pt(2.25)
        s.smooth = False
        s.marker.style = 8  # circle
        s.marker.size = 5
        s.marker.format.fill.solid()
        s.marker.format.fill.fore_color.rgb = col
        s.marker.format.line.color.rgb = col
    va = ch.value_axis
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE2, 0xE4, 0xEA)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(size - 1)
    va.tick_labels.font.color.rgb = GREY
    if vmin is not None:
        va.minimum_scale = vmin
    if vmax is not None:
        va.maximum_scale = vmax
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(size - 1)
    ca.format.line.color.rgb = RGBColor(0xC8, 0xCB, 0xD3)
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(size)
    if title:
        ch.has_title = True
        ch.chart_title.text_frame.text = title
        tp = ch.chart_title.text_frame.paragraphs[0]
        tp.runs[0].font.size = Pt(size + 1)
        tp.runs[0].font.bold = True
        tp.runs[0].font.color.rgb = DARK
    return ch


def header(slide, line2):
    """Second line of the template's question header."""
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.startswith("("):
            paras = sh.text_frame.paragraphs
            p = paras[1]
            runs = p.runs
            runs[0].text = line2
            runs[0].font.size = Pt(15)
            for r in runs[1:]:
                r._r.getparent().remove(r._r)
            for extra in paras[2:]:
                extra._p.getparent().remove(extra._p)
            sh.top = Inches(0.18)
            sh.height = Inches(0.62)
            sh.text_frame.vertical_anchor = MSO_ANCHOR.TOP
            return sh
    raise ValueError("no header")


def clone(prs, src):
    s = prs.slides.add_slide(src.slide_layout)
    for sh in list(s.shapes):
        sh._element.getparent().remove(sh._element)
    for sh in src.shapes:
        s.shapes._spTree.insert_element_before(copy.deepcopy(sh._element), "p:extLst")
    return s


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def card(slide, x, y, w, h, title, body, fill=INDIGO_LT, title_color=INDIGO, size=11):
    box(slide, x, y, w, h, fill=fill)
    text(slide, x + 0.15, y + 0.1, w - 0.3, 0.3, [[(title, {"bold": True, "color": title_color})]], size=size + 1)
    text(slide, x + 0.15, y + 0.42, w - 0.3, h - 0.5, body, size=size)


# --------------------------------------------------------------------------- build
prs = Presentation(ROOT / "slides" / "template.pptx")
title_s, q1, q2, q3, q4 = list(prs.slides)
# pristine copies of the question slides, made before anything is drawn on them
q1_period = clone(prs, q1)
q2_joins, q2_res = clone(prs, q2), clone(prs, q2)
q3_cap, q3_feat, q3_res = clone(prs, q3), clone(prs, q3), clone(prs, q3)
q4_proto, q4_res, q4_sum = clone(prs, q4), clone(prs, q4), clone(prs, q4)
order = []

# ---------------- 1. Title
for sh in title_s.shapes:
    if sh.has_text_frame and sh.text_frame.text.startswith("Assignment 2"):
        sh.top = Inches(1.15)
text(title_s, 1.0, 2.92, 8.0, 0.95, [
    {"runs": [("Malo Joannon", {"bold": True, "size": 14})], "align": PP_ALIGN.CENTER},
    {"runs": [("Student ID 315551818", {})], "align": PP_ALIGN.CENTER},
    {"runs": [("GitHub: ", {}), (REPO_URL, {"link": REPO_URL, "color": INDIGO})], "align": PP_ALIGN.CENTER},
], size=12, color=DARK)
notes(title_s, "Introduce the task: predict 6 GitHub activities for 4,465 test users in the week of Nov 22-29.")
order.append(title_s)

# ---------------- 2. Q1 schema graph (native)
s = q1
header(s, "Schema graph: 8 tables, 20 foreign keys (FK → referenced PK)")
TBL = {
    "IssueComments": (0.5, 1.0, ["PK comment_id", "FK issue_id → Issues", "FK repo_id → Repositories",
                                  "FK author_id → Users"]),
    "Issues": (0.5, 2.2, ["PK issue_id", "FK repo_id → Repositories", "FK author_id → Users",
                          "FK pull_request_id → PullRequests", "FK assignee_id → Users"]),
    "Pushes": (0.5, 3.65, ["PK push_id", "FK user_id → Users", "FK repo_id → Repositories"]),
    "Users": (3.88, 1.25, ["PK user_id", "github_user_id, login, is_bot,", "is_cohort, first_seen_at"]),
    "Repositories": (3.88, 2.35, ["PK repo_id", "name, owner_login, org_id, …"]),
    "PRReviewComments": (7.15, 0.9, ["PK comment_id", "FK pr_id → PullRequests", "FK repo_id → Repositories",
                                     "FK author_id → Users", "FK pull_request_review_id → PRReviews",
                                     "FK in_reply_to_id → PRReviewComments"]),
    "PRReviews": (7.15, 2.45, ["PK review_id", "FK pr_id → PullRequests", "FK repo_id → Repositories",
                               "FK reviewer_id → Users"]),
    "PullRequests": (7.15, 3.65, ["PK pr_id", "FK repo_id → Repositories", "FK author_id → Users",
                                  "FK merged_by_id → Users (known later)"]),
}
W, HDR, ROW = 2.25, 0.24, 0.165
row_y = {}
for name, (x, y, rows) in TBL.items():
    h = HDR + 0.06 + ROW * len(rows) + 0.05
    hub = name in ("Users", "Repositories")
    box(s, x, y, W, h, fill=WHITE, line=GREEN if hub else INDIGO, shape=MSO_SHAPE.RECTANGLE, line_w=1.0)
    hd = box(s, x, y, W, HDR, fill=GREEN if hub else INDIGO, shape=MSO_SHAPE.RECTANGLE)
    box_text(hd, [[(name, {"bold": True, "color": WHITE})]], size=10)
    paras = []
    for r in rows:
        if r.startswith("PK "):
            paras.append({"runs": [("PK  ", {"bold": True, "color": ORANGE}), (r[3:], {"bold": True})]})
        elif r.startswith("FK "):
            paras.append({"runs": [("FK  ", {"bold": True, "color": INDIGO}), (r[3:], {})]})
        else:
            paras.append({"runs": [(r, {"color": GREY})]})
    tb = text(s, x + 0.07, y + HDR + 0.05, W - 0.1, ROW * len(rows), paras, size=8, space_after=0)
    for p in tb.text_frame.paragraphs:
        p.line_spacing = Pt(ROW * 72)
    for i, r in enumerate(rows):
        row_y[(name, r.split()[1] if r[:3] in ("PK ", "FK ") else r)] = y + HDR + 0.05 + ROW * (i + 0.5)
pk = {n: row_y[(n, rows[0].split()[1])] for n, (_, _, rows) in TBL.items()}


def fk(src, col):
    return row_y[(src, col)]


L0, R0 = 0.5, 0.5 + W           # left column edges
L1, R1 = 3.88, 3.88 + W         # hub column
L2, R2 = 7.15, 7.15 + W         # right column
C_USR, C_REPO, C_OTH = GREEN, ORANGE, INDIGO
# left column -> hubs
for src, col, tgt in [("IssueComments", "author_id", "Users"), ("IssueComments", "repo_id", "Repositories"),
                      ("Issues", "author_id", "Users"), ("Issues", "assignee_id", "Users"),
                      ("Issues", "repo_id", "Repositories"), ("Pushes", "user_id", "Users"),
                      ("Pushes", "repo_id", "Repositories")]:
    arrow(s, R0, fk(src, col), L1, pk[tgt], color=C_USR if tgt == "Users" else C_REPO, width=1.0)
# right column -> hubs
for src, col, tgt in [("PRReviewComments", "author_id", "Users"), ("PRReviewComments", "repo_id", "Repositories"),
                      ("PRReviews", "reviewer_id", "Users"), ("PRReviews", "repo_id", "Repositories"),
                      ("PullRequests", "author_id", "Users"), ("PullRequests", "repo_id", "Repositories")]:
    arrow(s, L2, fk(src, col), R1, pk[tgt], color=C_USR if tgt == "Users" else C_REPO, width=1.0)
arrow(s, L2, fk("PullRequests", "merged_by_id"), R1, pk["Users"], color=C_USR, width=1.0, dash=True)
# Issues.pull_request_id -> PullRequests (under the hubs)
polyline(s, [(R0, fk("Issues", "pull_request_id")), (R0 + 0.3, fk("Issues", "pull_request_id")),
             (R0 + 0.3, 3.45), (L2 - 0.3, 3.45), (L2 - 0.3, pk["PullRequests"]), (L2, pk["PullRequests"])],
         color=C_OTH, width=1.0)
# IssueComments.issue_id -> Issues (left side)
polyline(s, [(L0, fk("IssueComments", "issue_id")), (L0 - 0.2, fk("IssueComments", "issue_id")),
             (L0 - 0.2, pk["Issues"]), (L0, pk["Issues"])], color=C_OTH, width=1.0)
# right side routes
for off, (src, col, tgt) in zip([0.1, 0.2, 0.3], [("PRReviewComments", "pull_request_review_id", "PRReviews"),
                                                  ("PRReviews", "pr_id", "PullRequests"),
                                                  ("PRReviewComments", "pr_id", "PullRequests")]):
    polyline(s, [(R2, fk(src, col)), (R2 + off, fk(src, col)), (R2 + off, pk[tgt]), (R2, pk[tgt])],
             color=C_OTH, width=1.0)
# self reference in_reply_to_id
polyline(s, [(R2, fk("PRReviewComments", "in_reply_to_id")), (R2 + 0.4, fk("PRReviewComments", "in_reply_to_id")),
             (R2 + 0.4, pk["PRReviewComments"]), (R2, pk["PRReviewComments"])], color=C_OTH, width=1.0)
# legend
lg = 3.75
text(s, 3.6, lg, 2.8, 1.45, [
    [("Edges: FK → referenced PK", {"bold": True})],
    [("━ ", {"color": GREEN, "bold": True}), ("to Users (8)   ", {}), ("━ ", {"color": ORANGE, "bold": True}),
     ("to Repositories (6)", {})],
    [("━ ", {"color": INDIGO, "bold": True}), ("between activity tables (6)", {})],
    [("╌ ", {"color": GREEN, "bold": True}), ("FK known only later (masked unless < t)", {})],
    [("PK", {"bold": True, "color": ORANGE}), (" primary key   ", {}), ("FK", {"bold": True, "color": INDIGO}),
     (" foreign key", {})],
], size=9, space_after=2)
notes(s, "Eight tables. Users and Repositories are the hubs: every activity table points to them. "
         "Activity tables also point to each other: comments to issues, reviews and review comments to PRs, "
         "review comments to reviews and to themselves (replies). merged_by_id is only known after the merge.")
order.append(s)

# ---------------- 3. Q1 dataset time period
s = q1_period
header(s, "Dataset time period: GH Archive 2026-09-01 → %s UTC" % DATA_END.strftime("%Y-%m-%d %H:%M"))
X0, X1 = 0.6, 9.4
d0, d1 = datetime(2026, 9, 1), datetime(2026, 11, 29)


def xd(d):
    return X0 + (X1 - X0) * (d - d0).total_seconds() / (d1 - d0).total_seconds()


ty = 1.75
segs = [(datetime(2026, 9, 1), datetime(2026, 10, 3, 16), GREY_LT, "history only"),
        (datetime(2026, 10, 3, 16), datetime(2026, 11, 14, 16), INDIGO_LT, "6 labelled weeks"),
        (datetime(2026, 11, 14, 16), DATA_END, GREEN_LT, ""),
        (datetime(2026, 11, 21, 16), datetime(2026, 11, 28, 16), ORANGE_LT, "test week")]
for a, b, col, lab in segs:
    r = box(s, xd(a), ty, xd(b) - xd(a), 0.42, fill=col, shape=MSO_SHAPE.RECTANGLE)
    box_text(r, [[(lab, {"bold": True, "color": DARK})]], size=9)
for k in range(7):
    c = datetime(2026, 10, 3, 16) + (datetime(2026, 10, 10) - datetime(2026, 10, 3)) * k
    arrow(s, xd(c), ty, xd(c), ty + 0.42, color=INDIGO, width=0.75, head=False)
box(s, xd(DATA_END), ty, xd(datetime(2026, 11, 21, 16)) - xd(DATA_END), 0.42, fill=None, line=GREY,
    shape=MSO_SHAPE.RECTANGLE, dash=True, line_w=0.75)
marks = [(datetime(2026, 9, 1), "Sep 1\ndata start", 0), (datetime(2026, 10, 3, 16), "Oct 3\n1st cutoff", 0),
         (datetime(2026, 11, 7, 16), "Nov 7\nlast cutoff", 0),
         (DATA_END, "Nov 14–" + DATA_END.strftime("%d %H:%M") + ": features only\ndata end", 1),
         (datetime(2026, 11, 21, 16), "Nov 21 16:00 UTC\ntest cutoff", 2)]
for d, lab, lvl in marks:
    x = xd(d)
    yy = ty + 0.5 + 0.0 * lvl
    al = PP_ALIGN.LEFT if lvl == 0 and d.month == 9 else PP_ALIGN.CENTER
    wx = 1.2 if lvl != 1 else 2.0
    xx = x if al == PP_ALIGN.LEFT else x - wx / 2
    if lvl == 1:
        xx -= 0.5
    if lvl == 2:
        xx += 0.18
    text(s, xx, yy if lvl != 1 else ty - 0.5, wx, 0.4, [{"runs": [(lab, {})], "align": al}], size=9, color=GREY)
cards = [
    ("GH Archive input", [f"{rep.get('hour_files', 1929):,} hourly files (~29 GB)",
                          "2026-09-01 00:00 → " + DATA_END.strftime("%m-%d %H:%M") + " UTC",
                          "built with the course preprocess.py"]),
    ("8 relational tables", [f"{rep['cohort_users_in_data']:,} cohort users seen",
                             f"{rep['table_rows']['PullRequests']:,} PRs · {rep['table_rows']['Issues']:,} issues",
                             f"{rep['table_rows']['Pushes']:,} pushes · {sum(rep['table_rows'].values()):,} rows"]),
    ("Time protocol", ["samples at weekly cutoffs Oct 3 → Nov 7", "label = activity in [t, t + 7 days)",
                       "test: Nov 22–29 Taiwan = Nov 21–28 16:00 UTC"]),
]
for i, (t, lines) in enumerate(cards):
    card(s, 0.5 + i * 3.05, 2.95, 2.85, 1.45, t, [{"runs": [(l_, {})], "bullet": True} for l_ in lines], size=10)
text(s, 0.5, 4.55, 9.0, 0.6, [[("Why this period: ", {"bold": True}),
                               ("preprocess.py ignores files before 2025-12-01; the model needs ≥ 4 weeks of "
                                "history before the first cutoff; recent weeks match the test week best "
                                "(GH Archive capture changed a lot in 2026, see Q3).", {})]], size=10)
notes(s, "Downloaded GH Archive from Sep 1 to the last published hour, ran the course preprocessing script. "
         "Six weekly cutoffs with full labels, the last partial week is used for features only. Times are UTC.")
order.append(s)

# ---------------- 4. Q2 relational join paths
s = q2
header(s, "Join paths from a user through repositories, PRs/issues and other users")
nodes = {"user": (0.55, 2.35, "User u", GREEN), "repo": (2.75, 1.05, "Repositories\nu worked in", ORANGE),
         "pr": (2.75, 2.35, "u's PRs / issues", INDIGO), "others": (4.9, 1.05, "Other users\nin those repos", GREY),
         "inc": (4.9, 2.35, "Reviews & comments\non u's PRs/issues", INDIGO),
         "newpr": (4.9, 3.65, "New PRs by others\nin u's repos", INDIGO)}
NW, NH = 1.75, 0.62
for k, (x, y, lab, col) in nodes.items():
    b = box(s, x, y, NW, NH, fill=WHITE, line=col, line_w=1.5)
    box_text(b, [[(l_, {"bold": i == 0, "size": 10 if i == 0 else 9})] for i, l_ in enumerate(lab.split("\n"))],
             size=10)


def mid(k, side):
    x, y, _, _ = nodes[k]
    return {"r": (x + NW, y + NH / 2), "l": (x, y + NH / 2), "t": (x + NW / 2, y), "b": (x + NW / 2, y + NH)}[side]


for a, sa, b_, sb, lab in [("user", "r", "repo", "l", "1"), ("user", "r", "pr", "l", "3"), ("repo", "r", "others", "l", "2"),
                           ("pr", "r", "inc", "l", "4"), ("repo", "b", "newpr", "l", "5")]:
    p1, p2 = mid(a, sa), mid(b_, sb)
    if a == "repo" and b_ == "newpr":
        polyline(s, [(p1[0] - 0.45, p1[1]), (p1[0] - 0.45, 3.96), p2], color=INDIGO, width=1.25)
        text(s, p1[0] - 0.4, 3.62, 0.3, 0.3, [[(lab, {"bold": True, "color": ORANGE})]], size=11)
    else:
        arrow(s, *p1, *p2, color=INDIGO, width=1.25)
        text(s, (p1[0] + p2[0]) / 2 - 0.05, (p1[1] + p2[1]) / 2 - 0.3, 0.3, 0.3,
             [[(lab, {"bold": True, "color": ORANGE})]], size=11)
text(s, 0.55, 3.15, 2.0, 0.9, [[("merged_by_id → u: ", {"bold": True}), ("maintainer role (6)", {})],
                               [("u's activity mix: ", {"bold": True}), ("ratios (7)", {})]], size=9, color=DARK)
feats = [
    ("1 User → Repository", "distinct repos, top-repo share, org-repo share"),
    ("2 Repository ← other users", "repo activity & users last week, collaborators and their activity"),
    ("3 User → own PRs", "open PRs at t, merged PRs, cross-repo PRs"),
    ("4 Incoming interactions", "reviews / review comments / comments received last 7 days"),
    ("5 Review demand", "new PRs opened by others in u's repos last 7 days"),
    ("6 Maintainer role", "PRs merged by u (merged_by_id) in 4 weeks"),
    ("7 Cross-table ratios", "reviews per PR, comments per issue, pushes per PR"),
]
text(s, 6.95, 0.98, 2.75, 4.2, [p for t, d in feats for p in (
    {"runs": [(t, {"bold": True, "color": INDIGO})], "space_after": 0, "size": 10},
    {"runs": [(d, {})], "space_after": 5, "size": 9})], size=9)
notes(s, "Instead of only counting the user's own rows, I join the user's events to the repositories, the PRs and "
         "issues, and the other users. Each join gives a feature family; all are computed at the cutoff time t.")
order.append(s)

# ---------------- 5. Q2 point-in-time joins
s = q2_joins
header(s, "Each join is computed point-in-time: only rows known before the cutoff t")
examples = [
    ("reviews_received_1w(u, t)",
     "PRReviews ⋈ PullRequests ON pr_id\nWHERE PullRequests.author_id = u AND reviewer_id ≠ u\n"
     "AND submitted_at ∈ [t − 7d, t)"),
    ("review_demand_1w(u, t)",
     "repos(u, 4 weeks) ⋈ PullRequests ON repo_id\nWHERE author_id ≠ u AND created_at ∈ [t − 7d, t)"),
    ("open_prs_authored(u, t)",
     "PullRequests WHERE author_id = u\nAND (closed_at IS NULL OR closed_at ≥ t)    ← known-later column"),
]
for i, (t_, sql) in enumerate(examples):
    y = 1.0 + i * 1.07
    box(s, 0.5, y, 5.6, 0.95, fill=GREY_LT)
    text(s, 0.65, y + 0.08, 5.3, 0.25, [[(t_, {"bold": True, "color": INDIGO, "font": "Courier New"})]], size=10)
    text(s, 0.65, y + 0.36, 5.3, 0.55, [[(l_, {"font": "Courier New"})] for l_ in sql.split("\n")], size=9,
         space_after=0)
card(s, 6.35, 1.0, 3.2, 1.95, "Leakage control", [
    {"runs": [("Rows kept only if their row time (first_seen_at / created_at) < t", {})], "bullet": True},
    {"runs": [("merged_at, merged_by_id, closed_at, state_reason, dismissed_at masked if ≥ t", {})],
     "bullet": True},
], size=10)
card(s, 6.35, 3.1, 3.2, 1.05, "All users, not just the cohort", [
    {"runs": [("Repository context counts every user in the tables (%d%% of users are non-cohort)"
               % round(100 - 100 * rep["cohort_users_in_data"] / rep["table_rows"]["Users"]), {})]}],
    fill=GREEN_LT, title_color=GREEN, size=10)
text(s, 0.5, 4.35, 9.0, 0.8, [[("Why: ", {"bold": True}),
                               ("a user's next-week activity is driven by their neighbourhood — a PR that "
                                "receives reviews needs a push and replies; a busy repository generates review "
                                "requests. These signals are invisible in the user's own counts.", {})]], size=10)
notes(s, "Three examples of relational features written as joins. Every join respects the cutoff: rows that "
         "appear after t are removed, and columns that are only known later are masked.")
order.append(s)

# ---------------- 6. Q2 results
s = q2_res
header(s, "Result: relational features help alone, but the full set overfits on top of temporal")
rows = [(COPY, "Copy last week"), ("Ablation: base only", "Base (8-week counts)"),
        ("Ablation: base + compact relational (no temporal)", "Base + compact relational"),
        ("Ablation: base + all relational (no temporal)", "Base + all relational"),
        ("Ablation: base + temporal (no relational)", "Base + temporal"),
        ("Ablation: all relational features", "Temporal + all relational"),
        (FINAL, "Final: temporal + compact relational")]
cats = [r[1] for r in rows]
vals = [S[r[0]] for r in rows]
cols = [GREY, GREY, ORANGE, ORANGE, INDIGO, INDIGO, GREEN]
bar_chart(s, 0.4, 0.95, 5.6, 3.6, cats, [("Score", vals)], [INDIGO], vmin=30, vmax=42, point_colors=cols,
          number_format="0.00", gap=45, size=9)
text(s, 0.5, 4.55, 5.4, 0.35, [[("Mean Score (%) over 3 validation weeks (Oct 24, Oct 31, Nov 7)", {"italic": True})]],
     size=9, color=GREY)
d_rel = S["Ablation: base + all relational (no temporal)"] - S["Ablation: base only"]
d_full = S["Ablation: all relational features"] - S["Ablation: base + temporal (no relational)"]
d_cmp = S[FINAL] - S["Ablation: base + temporal (no relational)"]
imp_rel = rep["importance_share_by_group"]["relational"] * 100
card(s, 6.25, 0.98, 3.35, 3.0, "Observations", [
    {"runs": [(f"+{d_rel:.1f} pts", {"bold": True, "color": ORANGE}),
              (" relational features alone vs. base", {})], "bullet": True, "space_after": 6},
    {"runs": [(f"{d_full:+.1f} pts", {"bold": True, "color": ORANGE}),
              (" adding all ~30 relational features on top of temporal: they overlap with temporal "
               "signals and training data is small → overfitting", {})], "bullet": True, "space_after": 6},
    {"runs": [(f"{d_cmp:+.1f} pts", {"bold": True, "color": GREEN}),
              (" compact set (10 features) — within noise, more stable on the latest week", {})],
     "bullet": True, "space_after": 6},
    {"runs": [(f"{imp_rel:.0f}%", {"bold": True, "color": INDIGO}),
              (" of the final model's gain importance; review_to_pr_ratio is the top relational feature",
               {})], "bullet": True},
], size=10)
notes(s, "Ablation on 3 validation weeks. Relational information is useful, but most of it is already captured by "
         "the temporal features of the same user; with few training weeks the full set overfits, so I kept "
         "a compact subset.")
order.append(s)

# ---------------- 7. Q3 discovery: capture level
s = q3
header(s, "Finding: GH Archive's capture level drives the activity we observe")
wk = [w["week_start"][5:] for w in weekly][1:]
line_chart(s, 0.4, 0.95, 4.7, 3.4, wk, [("open_pr", [float(w["open_pr_capture"]) for w in weekly][1:]),
                                       ("pr_review_comment", [float(w["pr_review_comment_capture"]) for w in weekly][1:]),
                                       ("push", [float(w["push_capture"]) for w in weekly][1:])],
           [INDIGO, ORANGE, GREEN], size=9, vmin=0, title="GH Archive capture level (1 = typical hour)")
bar_chart(s, 5.2, 0.95, 4.4, 3.4, wk, [("any activity", [int(w["any_active_users"]) for w in weekly][1:]),
                                      ("push", [int(w["push_active_users"]) for w in weekly][1:])],
          [INDIGO, GREEN], horizontal=False, labels=False, legend=True, gap=40, size=9)
text(s, 5.3, 4.32, 4.3, 0.3, [[("Active cohort users per week", {"italic": True})]], size=9, color=GREY)
text(s, 0.5, 4.55, 9.1, 0.65, [[("GH Archive volume changes ×3–4 between weeks and PushEvent almost disappears after "
                                 "Oct 24: the cohort's observed activity follows it (2,718 → 283 users pushing per "
                                 "week). A zero is often missing data, not inactivity.", {})]], size=10)
notes(s, "Before modelling time I measured the data itself. scripts/coverage.py counts every event type in every "
         "GH Archive hour. The capture level moves a lot, and the cohort's observed activity follows it.")
order.append(s)

# ---------------- 8. Q3 capture-aware modelling
s = q3_cap
header(s, "Capture-aware time modelling: measure, mask labels, correct features")
steps = [
    ("1  Measure", ["count each event type in every GH Archive hour (scripts/coverage.py)",
                    "capture c(h, a) = count / median count at the same hour of day",
                    "1 = typical hour, 0 = no data"]),
    ("2  Mask labels", ["a label week with c < 0.25 for activity a is not used to train, tune or score a",
                        "push: weeks of Oct 31 and Nov 7 masked",
                        "mirrors the official rule (missing activity not scored)"]),
    ("3  Correct features", ["capture of each lag week as a feature",
                             "capture-corrected rates: count_w / c_w",
                             "share of observed weeks with activity"]),
]
for i, (t_, lines) in enumerate(steps):
    x = 0.5 + i * 3.05
    card(s, x, 1.0, 2.85, 2.0, t_, [{"runs": [(l_, {})], "bullet": True, "space_after": 4} for l_ in lines],
         fill=[INDIGO_LT, ORANGE_LT, GREEN_LT][i], title_color=[INDIGO, ORANGE, GREEN][i], size=10)
    if i < 2:
        arrow(s, x + 2.87, 2.0, x + 3.03, 2.0, color=GREY, width=1.5)
nc = S["Ablation: no coverage features"]
card(s, 0.5, 3.25, 9.0, 1.35, "Test time", [
    {"runs": [("Data ends %s UTC, %d h before the test cutoff: test features are computed at the end of the data "
               "so that the gap does not look like inactivity." % (DATA_END.strftime("%b %d %H:%M"),
                                                                    round((datetime(2026, 11, 21, 16) - DATA_END)
                                                                          .total_seconds() / 3600) - 1), {})],
     "bullet": True},
    {"runs": [("Push thresholds come from weeks where push was observable. Capture features: "
               f"{S[FINAL]:.2f} vs {nc:.2f} without (small gain, mostly robustness).", {})], "bullet": True},
], fill=GREY_LT, title_color=DARK, size=10)
notes(s, "Three steps: measure the capture level of every hour, do not learn from label weeks without data, and "
         "give the model the capture level of each lag week so it can tell missing data from inactivity.")
order.append(s)

# ---------------- 9. Q3 temporal features + point-in-time
s = q3_feat
header(s, "Multi-scale temporal features on a strict point-in-time timeline")
# timeline sketch
tx0, tx1, tl_y = 0.6, 5.6, 1.45
box(s, tx0, tl_y, 3.6, 0.38, fill=INDIGO_LT, shape=MSO_SHAPE.RECTANGLE)
box(s, tx0 + 3.6, tl_y, 1.35, 0.38, fill=ORANGE_LT, shape=MSO_SHAPE.RECTANGLE)
for k in range(5):
    xk = tx0 + 3.6 - 0.9 * k
    arrow(s, xk, tl_y, xk, tl_y + 0.38, color=INDIGO, width=0.75, head=False)
for k, lab in enumerate(["w1", "w2", "w3", "w4"]):
    text(s, tx0 + 3.6 - 0.9 * (k + 1), tl_y + 0.09, 0.9, 0.25, [{"runs": [(lab, {"bold": True})],
                                                               "align": PP_ALIGN.CENTER}], size=9, color=INDIGO)
text(s, tx0 + 3.6, tl_y + 0.09, 1.35, 0.25, [{"runs": [("label week", {"bold": True})], "align": PP_ALIGN.CENTER}],
     size=9, color=ORANGE)
arrow(s, tx0 + 3.6, tl_y - 0.25, tx0 + 3.6, tl_y + 0.42, color=DARK, width=1.5, head=False)
text(s, tx0 + 3.25, tl_y - 0.48, 0.7, 0.22, [{"runs": [("cutoff t", {"bold": True})], "align": PP_ALIGN.CENTER}],
     size=9)
text(s, tx0, tl_y + 0.48, 5.0, 0.3, [[("features use rows with row time < t · 8-week aggregates · labels = [t, t+7d)",
                                       {"italic": True})]], size=9, color=GREY)
fam = [
    ("Weekly lags", "counts in w1…w4 per activity + all"), ("8-week aggregates", "active weeks, rate, total"),
    ("Exponential decay", "Σ 0.5^(w−1) · count_w"), ("Recency", "days since last action, per activity"),
    ("Bursts", "counts in the last 1 and 3 days"), ("Regularity", "active days in 14 d, trend w1 − mean(w2..w4)"),
    ("Life cycle", "tenure (first seen), weekend share"), ("Capture", "capture level & corrected rates (prev. slide)"),
]
for i, (t_, d) in enumerate(fam):
    x = 0.5 + (i % 2) * 2.6
    y = 2.6 + (i // 2) * 0.64
    box(s, x, y, 2.5, 0.56, fill=INDIGO_LT)
    text(s, x + 0.1, y + 0.05, 2.35, 0.5, [[(t_, {"bold": True, "color": INDIGO})], [(d, {})]], size=9, space_after=0)
card(s, 5.85, 1.0, 3.75, 3.25, "Training samples over time", [
    {"runs": [("6 weekly cutoffs (Oct 3 → Nov 7), every cohort user seen before t: "
               f"{sum(w['users'] for w in val['weeks'].values()):,} samples", {})], "bullet": True, "space_after": 6},
    {"runs": [("Same features at train and test time — the model learns how activity in the "
               "recent weeks maps to next week", {})], "bullet": True, "space_after": 6},
    {"runs": [("Lags limited to 4 weeks: older weeks belong to a different GH Archive capture regime "
               "(8 weeks: %.2f vs 4 weeks: %.2f)" % (S["Ablation: 8 lag weeks"], S[FINAL]), {})],
     "bullet": True, "space_after": 6},
    {"runs": [("Rolling-origin validation: train on the past, tune on the next week, score on the week after",
               {})], "bullet": True},
], size=10)
notes(s, "Time is modelled at several scales: last days, weekly lags, decayed momentum and recency. Every sample "
         "is built exactly like a test sample, at a cutoff t, with only past rows.")
order.append(s)

# ---------------- 10. Q3 results
s = q3_res
header(s, "Result: temporal features give the largest gain (+%.1f pts over base)"
       % (S["Ablation: base + temporal (no relational)"] - S["Ablation: base only"]))
rows = [(COPY, "Copy last week"), ("Ablation: base only", "Base (8-week counts)"),
        ("Ablation: base + weekly lags only", "Base + weekly lag counts"),
        ("Ablation: base + temporal (no relational)", "Base + all temporal"),
        ("Ablation: no coverage features", "Final without capture features"),
        ("Ablation: 8 lag weeks", "Final with 8 lag weeks"),
        (FINAL, "Final (4 lag weeks)")]
bar_chart(s, 0.4, 0.95, 5.4, 3.6, [r[1] for r in rows], [("Score", [S[r[0]] for r in rows])], [INDIGO],
          vmin=30, vmax=42, point_colors=[GREY, GREY, INDIGO, INDIGO, ORANGE, ORANGE, GREEN],
          number_format="0.00", gap=45, size=9)
text(s, 0.5, 4.55, 5.3, 0.35, [[("Mean Score (%) over 3 validation weeks", {"italic": True})]], size=9, color=GREY)
sh = rep["importance_share_by_group"]
top = list(rep["top_features"].keys())[:5]
box(s, 6.05, 0.98, 3.55, 1.5, fill=INDIGO_LT)
text(s, 6.2, 1.05, 3.3, 0.8, [[(f"{sh['temporal'] * 100:.0f}%", {"bold": True, "size": 36, "color": INDIGO})]], size=36)
text(s, 6.2, 1.85, 3.3, 0.6, [[("of the final model's gain importance is temporal "
                                f"(relational {sh['relational'] * 100:.0f}%, base {sh['base'] * 100:.0f}%)", {})]],
     size=10)
card(s, 6.05, 2.65, 3.55, 2.1, "Top features", [
    {"runs": [(f, {"font": "Courier New", "size": 9})], "bullet": True, "space_after": 2} for f in top] + [
    {"runs": [("Decayed momentum dominates: recent weeks matter most, older weeks still help.", {})],
     "space_after": 0}], size=10)
notes(s, "Weekly lags alone already beat the base; recency, decay and bursts add more. Eight lag weeks are not "
         "better than four because older weeks come from a different capture regime.")
order.append(s)

# ---------------- 11. Q4 framework figure
s = q4
header(s, "Framework: from GH Archive hours to 6 calibrated classifiers")
stages = [
    (0.45, 1.0, "GH Archive", "hourly .json.gz\nSep 1 → Nov 20", GREY_LT, GREY),
    (2.35, 1.0, "preprocess.py", "8 anonymized tables\n(course script)", GREY_LT, GREY),
    (2.35, 2.25, "coverage.py", "capture level per\nhour & event type", ORANGE_LT, ORANGE),
    (4.25, 1.0, "Point-in-time\nsnapshot at t", "row time < t\nmask known-later", INDIGO_LT, INDIGO),
    (6.15, 1.0, "Feature builder", "base · temporal ·\nrelational · capture", INDIGO_LT, INDIGO),
    (6.15, 2.25, "Labels [t, t+7d)", "masked if capture\n< 0.25", ORANGE_LT, ORANGE),
    (8.05, 1.0, "Samples", "6 weekly cutoffs\n(user, t) rows", INDIGO_LT, INDIGO),
]
SW, SH = 1.55, 1.0
for x, y, t_, d, f, c in stages:
    b = box(s, x, y, SW, SH, fill=f, line=c, line_w=1.0)
    box_text(b, [[(t_.split("\n")[0], {"bold": True, "color": c, "size": 10})]] +
             ([[(t_.split("\n")[1], {"bold": True, "color": c, "size": 10})]] if "\n" in t_ else []) +
             [[(l_, {"size": 8.5})] for l_ in d.split("\n")], size=9)
for a, b_ in [(0, 1), (1, 3), (3, 4), (4, 6)]:
    arrow(s, stages[a][0] + SW, stages[a][1] + SH / 2, stages[b_][0], stages[b_][1] + SH / 2, color=DARK, width=1.5)
arrow(s, 0.45 + SW / 2, 2.0, 0.45 + SW / 2, 2.75, color=DARK, width=1.5, head=False)
polyline(s, [(0.45 + SW / 2, 2.75), (2.35, 2.75)], color=DARK, width=1.5)
polyline(s, [(2.35 + SW, 2.75), (6.15, 2.75)], color=ORANGE, width=1.5)
polyline(s, [(2.35 + SW + 0.25, 2.75), (2.35 + SW + 0.25, 2.1), (6.15 + 0.3, 2.1), (6.15 + 0.3, 2.0)],
         color=ORANGE, width=1.0, dash=True)
polyline(s, [(6.15 + SW, 2.75), (8.05 + SW / 2, 2.75), (8.05 + SW / 2, 2.0)], color=DARK, width=1.5)
# model row
mrow = [
    (0.45, 3.5, "Rolling evaluation", "3 folds: train → tune\nthreshold → score"),
    (2.65, 3.5, "6 × LightGBM", "one per activity,\n3 seeds averaged"),
    (4.85, 3.5, "F1 thresholds", "per activity on the\nlast labelled week"),
    (7.05, 3.5, "Refit + predict", "all 6 weeks → test\nusers at test cutoff"),
]
for x, y, t_, d in mrow:
    b = box(s, x, y, 2.0, 0.95, fill=GREEN_LT, line=GREEN, line_w=1.0)
    box_text(b, [[(t_, {"bold": True, "color": GREEN, "size": 10})]] + [[(l_, {"size": 8.5})] for l_ in d.split("\n")])
for i in range(3):
    arrow(s, mrow[i][0] + 2.0, 3.975, mrow[i + 1][0], 3.975, color=DARK, width=1.5)
polyline(s, [(8.05 + SW / 2, 2.75), (8.05 + SW / 2, 3.2), (1.45, 3.2), (1.45, 3.5)], color=DARK, width=1.5)
text(s, 7.05, 4.55, 2.6, 0.6, [[("→ output_315551818.csv", {"bold": True, "color": GREEN})],
                               [("checked with scripts/evaluate.py", {"color": GREY})]], size=10)
text(s, 0.45, 4.6, 6.4, 0.5, [[("Reproduce: ", {"bold": True}),
                               ("bash scripts/run_all.sh", {"font": "Courier New"}),
                               ("  (download → preprocess → coverage → main.py → evaluate)", {"size": 9})]], size=10)
notes(s, "Top row: data. The course script builds the tables, my coverage script measures GH Archive. "
         "At each cutoff I take a point-in-time snapshot, build features and labels. Bottom row: model training, "
         "threshold tuning, final refit and prediction.")
order.append(s)

# ---------------- 12. Q4 protocol
s = q4_proto
header(s, "Training protocol: rolling-origin validation, then refit on all weeks")
cut_lab = ["Oct 3", "Oct 10", "Oct 17", "Oct 24", "Oct 31", "Nov 7", "Test"]
gx0, gy0, cw, rh = 2.0, 1.25, 0.95, 0.42
for j, c in enumerate(cut_lab):
    text(s, gx0 + j * cw, gy0 - 0.3, cw, 0.25, [{"runs": [(c, {"bold": True})], "align": PP_ALIGN.CENTER}], size=9)
plan = [("Fold 1 (score Oct 24)", "TTCV---"), ("Fold 2 (score Oct 31)", "TTTCV--"), ("Fold 3 (score Nov 7)", "TTTTCV-"),
        ("Final model", "TTTTTC-"), ("Final refit", "TTTTTTP")]
colmap = {"T": (INDIGO_LT, "train"), "C": (ORANGE_LT, "tune"), "V": (GREEN_LT, "score"), "P": (ORANGE, "predict"),
          "-": (None, "")}
for i, (lab, row) in enumerate(plan):
    y = gy0 + i * (rh + 0.08)
    text(s, 0.5, y + 0.1, 1.45, 0.3, [[(lab, {"bold": i >= 3})]], size=9)
    for j, ch_ in enumerate(row):
        f, t_ = colmap[ch_]
        if f is None:
            continue
        b = box(s, gx0 + j * cw + 0.03, y, cw - 0.06, rh, fill=f, shape=MSO_SHAPE.RECTANGLE)
        box_text(b, [[(t_, {"color": WHITE if ch_ == "P" else DARK, "bold": ch_ in "VP"})]], size=9)
card(s, 0.5, 3.85, 4.35, 1.25, "Model", [
    {"runs": [("LightGBM per activity: 300 trees, lr 0.03, 31 leaves, subsample 0.8 — 3 seeds averaged", {})],
     "bullet": True},
    {"runs": [("Threshold maximising F1 (grid 0.02–0.80) — F1 rewards recall on rare activities", {})],
     "bullet": True}], size=10)
card(s, 5.05, 3.85, 4.5, 1.25, "Why this protocol", [
    {"runs": [("Never trains on the future; thresholds tuned on a week the model has not seen", {})], "bullet": True},
    {"runs": [("3 scored weeks instead of 1: single-week differences < 1 pt are noise", {})], "bullet": True}],
     size=10)
notes(s, "Each fold trains on older weeks, tunes thresholds on the next week and scores the week after. The final "
         "model is tuned on the last week and refit on all six weeks before predicting the test week.")
order.append(s)

# ---------------- 13. Q4 results
s = q4_res
gain = S[FINAL] - S[COPY]
header(s, "Validation results: %.2f vs %.2f for copy-last-week (+%.1f pts)" % (S[FINAL], S[COPY], gain))
pa_f, pa_c = M[FINAL]["per_activity"], M[COPY]["per_activity"]
bar_chart(s, 0.4, 0.95, 5.6, 3.55, ["open\npr", "open\nissue", "issue\ncomment", "pr\nreview", "pr_review\ncomment",
                                     "push"], [("Copy last week", [pa_c[a] * 100 for a in ACTS]),
                                          ("Final model", [pa_f[a] * 100 for a in ACTS])],
          [RGBColor(0xB8, 0xBE, 0xCC), INDIGO], horizontal=False, legend=True, vmin=0, vmax=60, gap=60,
          number_format="0", size=9)
text(s, 0.5, 4.5, 5.5, 0.6, [[("F1 (%) per activity, mean of 3 weeks (push: only Oct 24 is observable)",
                               {"italic": True})]], size=9, color=GREY)
pw = val["per_week"]
tbl = s.shapes.add_table(4, 4, Inches(6.25), Inches(1.0), Inches(3.35), Inches(1.45)).table
hdrs = ["Week", "Copy", "Final", "Δ"]
for j, h_ in enumerate(hdrs):
    tbl.cell(0, j).text = h_
for i, wkn in enumerate(["Oct 24", "Oct 31", "Nov 7"]):
    c_, f_ = pw[COPY][i]["score"] * 100, pw[FINAL][i]["score"] * 100
    for j, v in enumerate([wkn, fmt(c_), fmt(f_), f"{f_ - c_:+.1f}"]):
        tbl.cell(i + 1, j).text = v
for r in range(4):
    for j in range(4):
        cell = tbl.cell(r, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = INDIGO if r == 0 else (WHITE if r % 2 else GREY_LT)
        for p in cell.text_frame.paragraphs:
            p.alignment = PP_ALIGN.CENTER
            for run in p.runs:
                run.font.size = Pt(10)
                run.font.name = FONT
                run.font.bold = r == 0
                run.font.color.rgb = WHITE if r == 0 else DARK
card(s, 6.25, 2.65, 3.35, 2.2, "Notes", [
    {"runs": [("Official scripts/evaluate.py on the Nov 7 week: ", {}),
              (fmt(pw[FINAL][-1]["score"] * 100), {"bold": True})], "bullet": True, "space_after": 4},
    {"runs": [("Largest gains on open_pr and issue_comment; pr_review_comment stays hardest (rare, "
               "partly missing data)", {})], "bullet": True, "space_after": 4},
    {"runs": [("Course reference scores were measured on the 9/27 week with a different capture level — "
               "not directly comparable", {})], "bullet": True},
], size=10)
notes(s, "The final model beats copy-last-week on every validation week and on every activity on average.")
order.append(s)

# ---------------- 14. Conclusion
s = q4_sum
hd_ = header(s, "Takeaways, limitations and next steps")
hd_.text_frame.paragraphs[0].runs[0].text = "Summary"
for r in hd_.text_frame.paragraphs[0].runs[1:]:
    r._r.getparent().remove(r._r)
cols3 = [
    ("Takeaways", INDIGO_LT, INDIGO, [
        "Data quality first: GH Archive capture explains most week-to-week changes",
        "Temporal features carry the signal (88% of importance, +3 pts)",
        "Relational joins help alone; a compact set avoids overfitting",
        f"Final: {S[FINAL]:.2f} vs {S[COPY]:.2f} (copy last week)"]),
    ("Limitations", ORANGE_LT, ORANGE, [
        "Capture level of the test week is unknown (assumed like recent weeks)",
        "Push is unobservable in recent weeks: push model learned from October",
        "Only 6 labelled weeks; data ends before the test cutoff"]),
    ("Next steps", GREEN_LT, GREEN, [
        "Relational deep learning (GNN with time encoding) on the same snapshots",
        "Learn per-week capture correction jointly with the model",
        "Add the GH Archive hours published after Nov 20 08:00 UTC for fresher test features"]),
]
for i, (t_, f, c, lines) in enumerate(cols3):
    card(s, 0.5 + i * 3.05, 1.0, 2.85, 2.55, t_, [{"runs": [(l_, {})], "bullet": True, "space_after": 6}
                                                  for l_ in lines], fill=f, title_color=c, size=10)
box(s, 0.5, 3.8, 9.0, 1.2, fill=GREY_LT)
text(s, 0.7, 3.92, 8.6, 1.0, [
    [("Code: ", {"bold": True}), (REPO_URL, {"link": REPO_URL, "color": INDIGO})],
    [("Reproduce: ", {"bold": True}), ("bash scripts/run_all.sh", {"font": "Courier New"}),
     ("   → output/output_315551818.csv (format checked with scripts/evaluate.py)", {})],
    [("Data source: ", {"bold": True}), ("GH Archive (gharchive.org), tables built with the course preprocess.py", {})],
], size=10, space_after=5)
notes(s, "Summary of the findings and what I would do next.")
order.append(s)

# reorder
sld = prs.slides._sldIdLst
want = [s.slide_id for s in order]
id_el = {int(el.get("id")): el for el in sld}
for el in list(sld):
    sld.remove(el)
for sid in want:
    sld.append(id_el[sid])
prs.save(OUT)
print("wrote", OUT, len(order), "slides")
