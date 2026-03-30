import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
from io import BytesIO, StringIO
from datetime import datetime
from typing import Dict, List, Optional
import config


def generate_whatsapp_text(
    report_data: Dict, location_name: str = "Boteco Bangalore"
) -> str:
    """Generate WhatsApp formatted text report."""

    date_str = report_data.get("date", datetime.now().strftime("%d-%b-%Y"))

    # Calculate payment breakdown percentages
    net_total = report_data.get("net_total", 0)
    cash_pct = (
        (report_data.get("cash_sales", 0) / net_total * 100) if net_total > 0 else 0
    )
    card_pct = (
        (report_data.get("card_sales", 0) / net_total * 100) if net_total > 0 else 0
    )
    gpay_pct = (
        (report_data.get("gpay_sales", 0) / net_total * 100) if net_total > 0 else 0
    )
    zomato_pct = (
        (report_data.get("zomato_sales", 0) / net_total * 100) if net_total > 0 else 0
    )

    # Status emoji
    pct_target = report_data.get("pct_target", 0)
    if pct_target >= 100:
        status_emoji = "✅"
        status_text = "Target Achieved!"
    elif pct_target >= 90:
        status_emoji = "⚠️"
        status_text = "Almost There"
    else:
        status_emoji = "🔴"
        status_text = "Below Target"

    # Category breakdown
    categories = report_data.get("categories", [])
    category_text = ""
    if categories:
        for cat in categories:
            cat_total = sum(c.get("amount", 0) for c in categories)
            cat_pct = (cat.get("amount", 0) / cat_total * 100) if cat_total > 0 else 0
            amount_str = config.CURRENCY_FORMAT.format(cat.get("amount", 0))
            category_text += (
                f"• {cat.get('category', 'N/A')}: {cat_pct:.0f}% ({amount_str})\n"
            )
    else:
        category_text = "• Data not available\n"

    # Build report
    report = f"""
━━━━━━━━━━━━━━━━━━━━━━
🥂 {location_name.upper()}
📅 End of Day Report
📆 {date_str}
━━━━━━━━━━━━━━━━━━━━━━

💰 SALES SUMMARY
• Gross Total: {config.CURRENCY_FORMAT.format(report_data.get("gross_total", 0))}
• Net Total: {config.CURRENCY_FORMAT.format(net_total)}
• Covers: {report_data.get("covers", 0)} | Turns: {report_data.get("turns", 0):.1f}
• APC: {config.CURRENCY_FORMAT.format(report_data.get("apc", 0))}

💳 PAYMENT BREAKDOWN
• Cash: {config.CURRENCY_FORMAT.format(report_data.get("cash_sales", 0))} ({cash_pct:.0f}%)
• GPay: {config.CURRENCY_FORMAT.format(report_data.get("gpay_sales", 0))} ({gpay_pct:.0f}%)
• Zomato: {config.CURRENCY_FORMAT.format(report_data.get("zomato_sales", 0))} ({zomato_pct:.0f}%)
• Card: {config.CURRENCY_FORMAT.format(report_data.get("card_sales", 0))} ({card_pct:.0f}%)

📊 VS TARGET
• Target: {config.CURRENCY_FORMAT.format(report_data.get("target", 0))}
• Achievement: {pct_target:.1f}%
{status_emoji} Status: {status_text}

🍽️ CATEGORY MIX
{category_text}👥 MTD SUMMARY
• Total Covers: {report_data.get("mtd_total_covers", 0):,}
• Net Sales: {config.CURRENCY_FORMAT.format(report_data.get("mtd_net_sales", 0))}
• Avg Daily: {config.CURRENCY_FORMAT.format(report_data.get("mtd_avg_daily", 0))}
• % of Target: {report_data.get("mtd_pct_target", 0):.1f}%
━━━━━━━━━━━━━━━━━━━━━━"""

    return report.strip()


def generate_report_image(
    report_data: Dict, location_name: str = "Boteco Bangalore"
) -> BytesIO:
    """Generate report as PNG image."""

    fig, ax = plt.subplots(figsize=(8, 12))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    date_str = report_data.get("date", datetime.now().strftime("%d-%b-%Y"))
    y_pos = 95

    # Background
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # Title
    ax.text(
        50,
        y_pos,
        f"🥂 {location_name.upper()}",
        fontsize=18,
        fontweight="bold",
        ha="center",
        va="top",
        color="#ffffff",
    )
    y_pos -= 5
    ax.text(
        50,
        y_pos,
        "End of Day Report",
        fontsize=14,
        ha="center",
        va="top",
        color="#cccccc",
    )
    y_pos -= 4
    ax.text(
        50, y_pos, f"📆 {date_str}", fontsize=12, ha="center", va="top", color="#888888"
    )
    y_pos -= 8

    # Divider
    ax.plot([10, 90], [y_pos + 2, y_pos + 2], color="#e94560", linewidth=2)
    y_pos -= 5

    # Sales Summary Section
    ax.text(
        15,
        y_pos,
        "💰 SALES SUMMARY",
        fontsize=12,
        fontweight="bold",
        va="top",
        color="#e94560",
    )
    y_pos -= 5

    metrics = [
        (
            "Gross Total:",
            config.CURRENCY_FORMAT.format(report_data.get("gross_total", 0)),
        ),
        ("Net Total:", config.CURRENCY_FORMAT.format(report_data.get("net_total", 0))),
        (
            f"Covers: {report_data.get('covers', 0)} | Turns: {report_data.get('turns', 0):.1f}",
            "",
        ),
        ("APC:", config.CURRENCY_FORMAT.format(report_data.get("apc", 0))),
    ]

    for label, value in metrics:
        ax.text(15, y_pos, label, fontsize=11, va="top", color="#ffffff")
        if value:
            ax.text(
                85,
                y_pos,
                value,
                fontsize=11,
                va="top",
                color="#4ecca3",
                ha="right",
                fontweight="bold",
            )
        y_pos -= 4

    y_pos -= 3

    # Payment Breakdown
    ax.text(
        15,
        y_pos,
        "💳 PAYMENT BREAKDOWN",
        fontsize=12,
        fontweight="bold",
        va="top",
        color="#e94560",
    )
    y_pos -= 5

    payments = [
        ("Cash:", report_data.get("cash_sales", 0)),
        ("GPay:", report_data.get("gpay_sales", 0)),
        ("Zomato:", report_data.get("zomato_sales", 0)),
        ("Card:", report_data.get("card_sales", 0)),
    ]

    for label, value in payments:
        ax.text(15, y_pos, label, fontsize=11, va="top", color="#ffffff")
        ax.text(
            85,
            y_pos,
            config.CURRENCY_FORMAT.format(value),
            fontsize=11,
            va="top",
            color="#4ecca3",
            ha="right",
        )
        y_pos -= 4

    y_pos -= 3

    # Target Achievement
    ax.text(
        15,
        y_pos,
        "📊 TARGET",
        fontsize=12,
        fontweight="bold",
        va="top",
        color="#e94560",
    )
    y_pos -= 5

    pct = report_data.get("pct_target", 0)
    target = report_data.get("target", 0)

    ax.text(15, y_pos, "Target:", fontsize=11, va="top", color="#ffffff")
    ax.text(
        85,
        y_pos,
        config.CURRENCY_FORMAT.format(target),
        fontsize=11,
        va="top",
        color="#4ecca3",
        ha="right",
    )
    y_pos -= 4

    ax.text(15, y_pos, "Achievement:", fontsize=11, va="top", color="#ffffff")
    color = "#4ecca3" if pct >= 100 else "#ffd93d" if pct >= 80 else "#e94560"
    ax.text(
        85,
        y_pos,
        f"{pct:.1f}%",
        fontsize=11,
        va="top",
        color=color,
        ha="right",
        fontweight="bold",
    )
    y_pos -= 4

    # Progress bar
    bar_width = 70
    bar_height = 3
    bar_x = 15
    bar_y = y_pos - 2

    ax.add_patch(
        patches.Rectangle(
            (bar_x, bar_y), bar_width, bar_height, facecolor="#333333", edgecolor="none"
        )
    )
    fill_width = min(bar_width, (pct / 100) * bar_width)
    ax.add_patch(
        patches.Rectangle(
            (bar_x, bar_y), fill_width, bar_height, facecolor=color, edgecolor="none"
        )
    )
    y_pos -= 8

    # MTD Summary
    ax.text(
        15,
        y_pos,
        "👥 MTD SUMMARY",
        fontsize=12,
        fontweight="bold",
        va="top",
        color="#e94560",
    )
    y_pos -= 5

    mtd_metrics = [
        ("Total Covers:", f"{report_data.get('mtd_total_covers', 0):,}"),
        (
            "Net Sales:",
            config.CURRENCY_FORMAT.format(report_data.get("mtd_net_sales", 0)),
        ),
        (
            "Avg Daily:",
            config.CURRENCY_FORMAT.format(report_data.get("mtd_avg_daily", 0)),
        ),
        ("% of Target:", f"{report_data.get('mtd_pct_target', 0):.1f}%"),
    ]

    for label, value in mtd_metrics:
        ax.text(15, y_pos, label, fontsize=11, va="top", color="#ffffff")
        ax.text(85, y_pos, value, fontsize=11, va="top", color="#4ecca3", ha="right")
        y_pos -= 4

    # Footer
    y_pos -= 3
    ax.plot([10, 90], [y_pos + 2, y_pos + 2], color="#e94560", linewidth=1)
    ax.text(
        50,
        y_pos - 2,
        f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}",
        fontsize=9,
        ha="center",
        va="top",
        color="#666666",
    )

    plt.tight_layout()

    # Save to BytesIO
    img_buffer = BytesIO()
    plt.savefig(
        img_buffer,
        format="png",
        dpi=150,
        facecolor="#1a1a2e",
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.5,
    )
    plt.close(fig)

    img_buffer.seek(0)
    return img_buffer


def generate_simple_text_report(report_data: Dict) -> str:
    """Generate simple text report without emojis."""

    date_str = report_data.get("date", datetime.now().strftime("%d-%b-%Y"))

    lines = [
        "=" * 50,
        "BOTECO BANGALORE",
        "End of Day Report",
        f"Date: {date_str}",
        "=" * 50,
        "",
        "SALES SUMMARY",
        "-" * 30,
        f"Gross Total: {config.CURRENCY_FORMAT.format(report_data.get('gross_total', 0))}",
        f"Net Total: {config.CURRENCY_FORMAT.format(report_data.get('net_total', 0))}",
        f"Covers: {report_data.get('covers', 0)}",
        f"Turns: {report_data.get('turns', 0):.1f}",
        f"APC: {config.CURRENCY_FORMAT.format(report_data.get('apc', 0))}",
        "",
        "PAYMENT BREAKDOWN",
        "-" * 30,
        f"Cash: {config.CURRENCY_FORMAT.format(report_data.get('cash_sales', 0))}",
        f"GPay: {config.CURRENCY_FORMAT.format(report_data.get('gpay_sales', 0))}",
        f"Zomato: {config.CURRENCY_FORMAT.format(report_data.get('zomato_sales', 0))}",
        f"Card: {config.CURRENCY_FORMAT.format(report_data.get('card_sales', 0))}",
        "",
        "TARGET",
        "-" * 30,
        f"Target: {config.CURRENCY_FORMAT.format(report_data.get('target', 0))}",
        f"Achievement: {report_data.get('pct_target', 0):.1f}%",
        "",
        "MTD SUMMARY",
        "-" * 30,
        f"Total Covers: {report_data.get('mtd_total_covers', 0):,}",
        f"Net Sales: {config.CURRENCY_FORMAT.format(report_data.get('mtd_net_sales', 0))}",
        f"Avg Daily: {config.CURRENCY_FORMAT.format(report_data.get('mtd_avg_daily', 0))}",
        f"% of Target: {report_data.get('mtd_pct_target', 0):.1f}%",
        "=" * 50,
    ]

    return "\n".join(lines)


def generate_comparison_text(
    reports: List[Dict], location_name: str = "Boteco Bangalore"
) -> str:
    """Generate comparison report between multiple days."""

    if not reports:
        return "No data to compare"

    lines = [
        "=" * 50,
        f"{location_name.upper()}",
        "Daily Comparison Report",
        "=" * 50,
        "",
    ]

    for i, report in enumerate(reports, 1):
        date_str = report.get("date", "N/A")
        net = report.get("net_total", 0)

        if i > 1:
            prev = reports[i - 2]
            prev_net = prev.get("net_total", 0)
            diff = net - prev_net
            diff_pct = ((diff / prev_net) * 100) if prev_net > 0 else 0
            arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
            comparison = f" ({arrow} {diff_pct:+.1f}%)"
        else:
            comparison = ""

        lines.extend(
            [
                f"📅 {date_str}",
                f"   Net Sales: {config.CURRENCY_FORMAT.format(net)}{comparison}",
                f"   Covers: {report.get('covers', 0)} | APC: {config.CURRENCY_FORMAT.format(report.get('apc', 0))}",
                "",
            ]
        )

    return "\n".join(lines)
