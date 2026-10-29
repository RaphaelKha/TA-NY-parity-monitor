"""Figures for the README, from the 1m bars on disk (same computation as parity_track.py).

    python plot_parity.py   # writes figures/<name>-light.png and figures/<name>-dark.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import ROOT, load_config
from parity_track import episodes, load_bars, pair_gaps

FIG = ROOT / "figures"
PAIRS = ["TEVA", "NICE", "ESLT", "ICL"]  # fixed order = fixed colour per pair in every figure
MIN_SESSION_MIN = 15  # sessions with fewer common minutes (e.g. the first, partial day) are left out of fig. 4
THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9",
                  axis="#c3c2b7", series=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a",
                 axis="#383835", series=["#3987e5", "#d95926", "#199e70", "#c98500"]),
}


def load_gaps():
    cfg = load_config()
    fx = load_bars(cfg["fx"])
    out = {}
    for pair in PAIRS:
        p = cfg["pairs"][pair]
        out[pair] = pair_gaps(load_bars(pair), load_bars(p["tase"]), fx, p["ratio"], cfg["bias_window_min"])
    return cfg, out


def style(ax, th):
    ax.set_facecolor(th["surface"])
    ax.grid(axis="y", color=th["grid"], linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(th["axis"])
    ax.tick_params(colors=th["muted"], labelsize=8, length=0, pad=4)
    ax.yaxis.label.set_color(th["ink2"])
    ax.xaxis.label.set_color(th["ink2"])


def new_fig(th, nrows, ncols, size, title, subtitle, **kw):
    fig, axes = plt.subplots(nrows, ncols, figsize=size, facecolor=th["surface"], squeeze=False, **kw)
    fig.text(0.012, 0.985, title, color=th["ink"], fontsize=12, fontweight="bold", va="top")
    fig.text(0.012, 0.935, subtitle, color=th["ink2"], fontsize=9, va="top")
    for ax in axes.flat:
        style(ax, th)
    return fig, axes


def footer(fig, th, text):
    fig.text(0.012, 0.012, text, color=th["muted"], fontsize=7.5, va="bottom")


def fig_timeline(gaps, th):
    """Gap per common minute, sessions laid end to end; the trailing median is the 'usual bias'."""
    fig, axes = new_fig(th, 4, 1, (10, 8.2), "Tel Aviv / New York gap, every common minute",
                        "Thin line: gap each minute.  Thick line: usual bias (median of the previous 300 common minutes).  "
                        "Sessions laid end to end.", sharey=True)
    for i, (ax, pair) in enumerate(zip(axes[:, 0], PAIRS)):
        d = gaps[pair]
        x = np.arange(len(d))
        c = th["series"][i]
        ax.axhline(0, color=th["axis"], linewidth=0.8)
        ax.plot(x, d.gap_bps, color=c, linewidth=0.7, alpha=0.45)
        ax.plot(x, d.bias_bps, color=c, linewidth=2)
        starts = np.flatnonzero(np.r_[True, d.index.date[1:] != d.index.date[:-1]])
        for s in starts[1:]:
            ax.axvline(s - 0.5, color=th["grid"], linewidth=0.6)
        ax.set_xticks(starts[::2], [pd.Timestamp(d.index[s]).strftime("%d %b") for s in starts[::2]])
        ax.set_xlim(-1, len(d))
        ax.set_ylim(-80, 60)
        ax.text(0.005, 0.93, pair, transform=ax.transAxes, color=th["ink"], fontsize=10, fontweight="bold", va="top")
        ax.text(0.995, 0.93, f"median gap, all minutes: {d.gap_bps.median():+.1f} bp", transform=ax.transAxes,
                color=th["ink2"], fontsize=8, va="top", ha="right")
        ax.set_ylabel("bp")
    footer(fig, th, "Gap = New York price / Tel Aviv price in USD − 1, in basis points (1 bp = 0.01%).  "
                    "Source: Yahoo Finance 1-minute bars, last-trade prices.")
    fig.tight_layout(rect=(0, 0.025, 1, 0.92), h_pad=1.2)
    return fig


def fig_distribution(gaps, cfg, th):
    """How far the gap strays from its usual level, against the round-trip costs tested."""
    fig, axes = new_fig(th, 2, 2, (10, 6.2), "How far the gap moves away from its usual level",
                        "Share of common minutes by deviation from the usual bias.  "
                        "Dotted hairlines: round-trip costs tested (±20, ±40, ±60 bp).", sharex=True, sharey=True)
    bins = np.arange(-80, 64, 4)
    for i, (ax, pair) in enumerate(zip(axes.flat, PAIRS)):
        dev = gaps[pair].dev_bps
        w = np.full(len(dev), 100 / len(dev))
        ax.hist(dev.clip(-79.9, 59.9), bins=bins, weights=w, color=th["series"][i], rwidth=0.82)
        for t in cfg["thresholds_bps"]:
            for s in (-t, t):
                ax.axvline(s, color=th["muted"], linewidth=0.7, linestyle=(0, (1, 2)))
        beyond = {t: (dev.abs() > t).mean() for t in cfg["thresholds_bps"]}
        ax.text(0.02, 0.93, pair, transform=ax.transAxes, color=th["ink"], fontsize=10, fontweight="bold", va="top")
        ax.text(0.98, 0.93, "\n".join(f"beyond ±{t} bp: {v:.1%}" for t, v in beyond.items()),
                transform=ax.transAxes, color=th["ink2"], fontsize=8, va="top", ha="right")
        ax.set_xlim(-80, 60)
    for ax in axes[1]:
        ax.set_xlabel("deviation from usual bias (bp)")
    for ax in axes[:, 0]:
        ax.set_ylabel("% of minutes")
    footer(fig, th, f"{sum(len(g) for g in gaps.values())} common minutes, "
                    f"{min(g.index.min() for g in gaps.values()):%d %b} – {max(g.index.max() for g in gaps.values()):%d %b %Y}.  "
                    "Values beyond the axis are piled into the end bins.")
    fig.tight_layout(rect=(0, 0.03, 1, 0.9))
    return fig


def fig_durations(gaps, cfg, th):
    """Survival of episodes: how many last at least k minutes. Only k >= min_run leaves time to trade both legs."""
    ks = np.arange(1, 9)
    thresholds = cfg["thresholds_bps"]
    fig, axes = new_fig(th, 1, len(thresholds), (10, 4.2), "How long does a wide gap last?",
                        f"Number of episodes (consecutive minutes beyond the cost, same side) lasting at least k minutes.  "
                        f"Shaded: ≥ {cfg['min_run_min']} min, enough time to trade both legs.", sharey=True)
    for ax, t in zip(axes[0], thresholds):
        ax.axvspan(cfg["min_run_min"] - 0.3, ks[-1] + 0.3, color=th["grid"], alpha=0.6, linewidth=0)
        for i, pair in enumerate(PAIRS):
            ep = pd.concat([episodes(d.dev_bps, t) for _, d in gaps[pair].groupby(gaps[pair].index.date)])
            n = [(ep >= k).sum() for k in ks]
            ax.plot(ks, n, color=th["series"][i], linewidth=2, marker="o", markersize=5,
                    markeredgecolor=th["surface"], markeredgewidth=1.2, label=pair)
        ax.set_title(f"cost {t} bp", color=th["ink"], fontsize=10, loc="left")
        ax.set_xticks(ks)
        ax.set_xlabel("minimum duration k (minutes)")
    axes[0][0].set_ylabel("episodes")
    leg = axes[0][-1].legend(frameon=False, fontsize=8, loc="upper right")
    for text in leg.get_texts():
        text.set_color(th["ink2"])
    footer(fig, th, "1-minute episodes are mostly last-trade prices bouncing between bid and ask, so counts are an upper bound.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.86))
    return fig


def fig_sessions(gaps, th):
    """Per session: 95th percentile of |deviation|, with the election marked."""
    fig, axes = new_fig(th, 1, 1, (10, 4.4), "Did the gap widen around the election?",
                        "95th percentile of |deviation from usual bias| in each session.  "
                        f"Sessions with fewer than {MIN_SESSION_MIN} common minutes left out.")
    ax = axes[0][0]
    for i, pair in enumerate(PAIRS):
        d = gaps[pair]
        s = d.dev_bps.abs().groupby(d.index.date).agg(["size", lambda x: x.quantile(.95)])
        s = s[s["size"] >= MIN_SESSION_MIN].iloc[:, 1]
        x = pd.to_datetime(s.index)
        ax.plot(x, s.values, color=th["series"][i], linewidth=2, marker="o", markersize=5,
                markeredgecolor=th["surface"], markeredgewidth=1.2)
        ax.annotate(pair, (x[-1], s.values[-1]), xytext=(8, 0), textcoords="offset points",
                    color=th["ink2"], fontsize=8, va="center")
    for day, label, ha in (("2026-10-25", "Israel to winter time:\ncommon window 1h → 2h", "right"),
                           ("2026-10-27", "Election day\n(Tel Aviv closed)", "left")):
        ax.axvline(pd.Timestamp(day), color=th["muted"], linewidth=0.8)
        pad = " " if ha == "left" else ""
        ax.text(pd.Timestamp(day), ax.get_ylim()[1], "\n".join(pad + s + ("" if pad else " ") for s in label.split("\n")),
                color=th["ink2"], fontsize=7.5, va="top", ha=ha, multialignment=ha)
    ax.set_ylabel("bp")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    ax.set_xlim(right=ax.get_xlim()[1] + 1.2)
    footer(fig, th, "No common window on Fridays (Tel Aviv closes before New York opens) or on 27 Oct.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.88))
    return fig


def main():
    cfg, gaps = load_gaps()
    FIG.mkdir(exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"
    for mode, th in THEMES.items():
        for name, fig in (("gap-timeline", fig_timeline(gaps, th)), ("deviation", fig_distribution(gaps, cfg, th)),
                          ("durations", fig_durations(gaps, cfg, th)), ("sessions", fig_sessions(gaps, th))):
            fig.savefig(FIG / f"{name}-{mode}.png", dpi=160, facecolor=th["surface"])
            plt.close(fig)
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
