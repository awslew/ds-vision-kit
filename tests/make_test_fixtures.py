#!/usr/bin/env python3
"""Generate the synthetic test images in tests/images/ with PIL only (no
Chrome, no vision API, no network). Run it to rebuild the fixtures:

    python tests/make_test_fixtures.py

The images are designed to exercise the vision core on NON-UI content:
document table, text page, labeled chart, unlabeled chart. Ground-truth values
are hard-coded here so references/accuracy.md measurements stay reproducible.
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "images"
OUT.mkdir(parents=True, exist_ok=True)


def font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf",
                 "C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- chart (labeled)
def make_chart_labeled() -> None:
    W, H = 900, 560
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_title, f_label, f_axis = font(22), font(14), font(12)

    d.text((40, 24), "2026 年上半年各季度营收（万元）", fill="black", font=f_title)
    margin_l, margin_b = 90, 70
    cx0, cy1 = margin_l, 60
    cx1, cy0 = W - 40, H - margin_b
    plot_w, plot_h = cx1 - cx0, cy0 - cy1
    vals = [320, 480, 610, 720]
    labels = ["Q1", "Q2", "Q3", "Q4"]
    ymax = 800
    n = len(vals)
    bar_w = 70
    gap = (plot_w - n * bar_w) / (n + 1)

    for v in range(0, ymax + 1, 200):
        y = cy1 + plot_h - plot_h * v / ymax
        d.line([(cx0, y), (cx1, y)], fill="#dddddd", width=1)
        d.text((cx0 - 12, y - 8), str(v), fill="#555", font=f_axis, anchor="rm")

    for i, v in enumerate(vals):
        x0 = cx0 + gap + i * (bar_w + gap)
        hh = plot_h * v / ymax
        d.rectangle([x0, cy0 - hh, x0 + bar_w, cy0], fill="#4c78a8")
        d.text((x0 + bar_w / 2, cy0 - hh - 22), str(v), fill="#4c78a8", font=f_label, anchor="mm")
        d.text((x0 + bar_w / 2, cy0 + 14), labels[i], fill="#333", font=f_label, anchor="mm")

    pts = [(cx0 + gap + bar_w / 2 + i * (bar_w + gap), cy1 + plot_h - plot_h * 500 / ymax)
           for i in range(n)]
    d.line(pts, fill="#e45756", width=3)
    d.text((pts[0][0] - 6, pts[0][1] - 24), "目标 500", fill="#e45756", font=f_axis)
    d.line([(cx0, cy0), (cx1, cy0)], fill="#333", width=2)
    d.line([(cx0, cy1), (cx0, cy0)], fill="#333", width=2)
    d.rectangle([W - 260, 30, W - 30, 62], outline="#ccc", fill="#fafafa")
    d.rectangle([W - 245, 40, W - 225, 55], fill="#4c78a8")
    d.text((W - 218, 38), "营收", fill="#333", font=f_axis)
    d.line([(W - 160, 47), (W - 130, 47)], fill="#e45756", width=3)
    d.text((W - 123, 38), "目标线", fill="#333", font=f_axis)

    img.save(OUT / "chart_barline.png")
    print("wrote chart_barline.png")


# ---------------------------------------------------------------- chart (unlabeled)
def make_chart_unlabeled() -> None:
    W, H = 760, 480
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_title, f_axis, f_label = font(18), font(12), font(13)

    d.text((30, 18), "月度新增用户数（人）", fill="black", font=f_title)
    margin_l, margin_b = 70, 60
    cx0, cy1 = margin_l, 40
    cx1, cy0 = W - 30, H - margin_b
    plot_w, plot_h = cx1 - cx0, cy0 - cy1
    vals = [240, 520, 380, 710, 460, 890]   # ground truth (used by accuracy.md)
    labels = ["1月", "2月", "3月", "4月", "5月", "6月"]
    ymax = 1000
    n = len(vals)
    bar_w = 42
    gap = (plot_w - n * bar_w) / (n + 1)

    for v in range(0, ymax + 1, 200):
        y = cy1 + plot_h - plot_h * v / ymax
        d.line([(cx0, y), (cx1, y)], fill="#dddddd", width=1)
        d.text((cx0 - 10, y - 8), str(v), fill="#555", font=f_axis, anchor="rm")

    for i, v in enumerate(vals):
        x0 = cx0 + gap + i * (bar_w + gap)
        hh = plot_h * v / ymax
        d.rectangle([x0, cy0 - hh, x0 + bar_w, cy0], fill="#57a0b5")
        d.text((x0 + bar_w / 2, cy0 + 12), labels[i], fill="#333", font=f_label, anchor="mm")

    d.line([(cx0, cy0), (cx1, cy0)], fill="#333", width=2)
    d.line([(cx0, cy1), (cx0, cy0)], fill="#333", width=2)
    img.save(OUT / "chart_nolabel.png")
    print("wrote chart_nolabel.png")


# ---------------------------------------------------------------- document table
def make_table_doc() -> None:
    W, H = 1000, 620
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_h1, f_h2, f_cell = font(24), font(17), font(15)

    d.text((40, 28), "2026年第二季度销售报表", fill="#111", font=f_h1)
    d.text((42, 62), "单位：万元 | 数据来源：财务系统导出", fill="#666", font=f_h2)

    cols = ["产品线", "四月", "五月", "六月", "季度合计", "同比"]
    rows = [
        ["智能家居", "128.5", "135.2", "149.8", "413.5", "+12.3%"],
        ["穿戴设备", "86.3", "92.1", "88.7", "267.1", "+6.8%"],
        ["企业服务", "204.0", "198.4", "215.6", "618.0", "+9.1%"],
        ["内容订阅", "45.2", "47.8", "51.3", "144.3", "+15.4%"],
        ["合计", "463.9", "473.5", "505.4", "1442.8", "+10.8%"],
    ]
    x0, y0, cw = 40, 100, [150, 100, 100, 100, 130, 110]
    ch = 44
    for ci, header in enumerate(cols):
        d.rectangle([x0 + sum(cw[:ci]), y0, x0 + sum(cw[:ci + 1]), y0 + ch], fill="#e8e8e8", outline="#999")
        d.text((x0 + sum(cw[:ci]) + 10, y0 + 10), header, fill="#111", font=f_h2)
    for ri, row in enumerate(rows):
        y = y0 + (ri + 1) * ch
        is_total = ri == len(rows) - 1
        fill = "#f5f5f5" if is_total else "white"
        for ci, cell in enumerate(row):
            x = x0 + sum(cw[:ci])
            d.rectangle([x, y, x + cw[ci], y + ch], fill=fill, outline="#999")
            d.text((x + 10, y + 10), cell, fill="#111", font=f_cell)

    img.save(OUT / "table_doc.png")
    print("wrote table_doc.png")


# ---------------------------------------------------------------- text page
def make_page_doc() -> None:
    W, H = 800, 700
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_h1, f_p, f_code = font(22), font(16), font(15)

    d.text((40, 30), "服务器部署手册（节选）", fill="#111", font=f_h1)
    d.text((42, 72), "本文档说明如何在一台 Ubuntu 22.04 服务器上通过 Docker 部署", fill="#333", font=f_p)
    d.text((42, 100), "nginx 反向代理，并启用 HTTPS。", fill="#333", font=f_p)
    d.text((42, 150), "第一步：安装 Docker", fill="#111", font=f_p)
    d.rectangle([40, 185, 760, 225], fill="#f4f4f4", outline="#ddd")
    d.text((52, 195), "sudo apt update && sudo apt install -y docker.io docker-compose", fill="#333", font=f_code)
    d.text((42, 250), "第二步：编写 docker-compose.yml", fill="#111", font=f_p)
    d.rectangle([40, 285, 760, 325], fill="#f4f4f4", outline="#ddd")
    d.text((52, 295), 'services:\\n  nginx:\\n    image: nginx:1.25', fill="#333", font=f_code)
    d.text((42, 350), "第三步：配置 HTTPS 证书", fill="#111", font=f_p)
    d.rectangle([40, 385, 760, 425], fill="#f4f4f4", outline="#ddd")
    d.text((52, 395), "sudo certbot --nginx -d example.com", fill="#333", font=f_code)
    d.rectangle([40, 455, 760, 515], fill="#fafafa", outline="#ccc")
    d.text((52, 465), "注意：证书有效期 90 天，建议配置 cron 自动续期，", fill="#333", font=f_p)
    d.text((52, 493), "否则过期后网站会报安全错误。", fill="#333", font=f_p)
    d.text((42, 545), "最后重启服务：", fill="#333", font=f_p)
    d.rectangle([40, 580, 760, 620], fill="#f4f4f4", outline="#ddd")
    d.text((52, 590), "sudo docker compose up -d", fill="#333", font=f_code)

    img.save(OUT / "page_doc.png")
    print("wrote page_doc.png")


if __name__ == "__main__":
    make_chart_labeled()
    make_chart_unlabeled()
    make_table_doc()
    make_page_doc()
    print("done. images written to", OUT)
