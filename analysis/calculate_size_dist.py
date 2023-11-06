#!/usr/bin/env python
"""Make a KDE plot of file size distribution."""
from pathlib import Path
from typing import Annotated
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import typer
from scipy.stats import norm


DEFAULT_INPUT = Path("PDB_random_1000_sizes.tsv")
DEFAULT_OUTPUT = Path("../docs/_static/file_size_distribution.png")
DEFAULT_NPOINTS = 50
DOWNSAMPLE_PERCENT = 5


def main(
    input_tsv: Annotated[Optional[Path], typer.Option()] = None,
    plot_file: Annotated[Optional[Path], typer.Option()] = None,
    npoints: int = DEFAULT_NPOINTS,
    logspace: bool = True,
    show: bool = False,
):
    """Plot histogram of sizes against various distributions."""
    if input_tsv is None:
        input_tsv = DEFAULT_INPUT
    if plot_file is None:
        plot_file = DEFAULT_OUTPUT
    df = pd.read_csv(input_tsv, sep="\t", index_col=0)
    lindata = df["size"]
    logdata = np.log10(lindata)
    data = logdata if logspace else lindata
    plt.rcParams.update({"font.size": 14})
    sns.histplot(
        data=data,
        color="k",
        stat="density",
        fill=False,
        bins=npoints,
    )
    ax = sns.kdeplot(
        data=data,
        linewidth=2,
        label="KDE",
        color="b",
        gridsize=npoints,
    )
    x = ax.lines[0].get_xdata()  # Get the x data of the distribution
    y = ax.lines[0].get_ydata()  # Get the y data of the distribution
    mu, std = norm.fit(lindata)
    print(f"norm mu={mu}, std={std}")
    norm_p = norm.pdf(10.0**x, mu, std)
    norm_p = norm_p * 1.0 / max(norm_p)
    plt.plot(
        x,
        norm_p,
        "g",
        linewidth=2,
        label="Norm 100%",
        linestyle="dotted",
    )
    np.random.seed(87507)
    ds_lindata = np.random.choice(
        lindata, size=int(len(lindata) * DOWNSAMPLE_PERCENT / 100.0)
    )
    ds_mu, ds_std = norm.fit(ds_lindata)
    print(f"norm [{DOWNSAMPLE_PERCENT}] mu={ds_mu}, std={ds_std}")
    ds_norm_p = norm.pdf(10.0**x, ds_mu, ds_std)
    ds_norm_p = ds_norm_p * 1.0 / max(ds_norm_p)
    plt.plot(
        x,
        ds_norm_p,
        "g",
        linewidth=2,
        label=f"Norm {DOWNSAMPLE_PERCENT}%",
        linestyle="dashed",
    )
    log_mu, log_std = norm.fit(logdata)
    print(f"log norm mu={log_mu}, std={log_std}")
    lognorm_p = norm.pdf(x, log_mu, log_std)
    plt.plot(x, lognorm_p, "r", linewidth=2, label="Log norm")
    maxid = np.argmax(y)  # The id of the peak (maximum of y data)
    x_max = x[maxid]
    y_max = y[maxid]
    if logspace:
        mode = int(round(10.0**x_max / 1024.0, 0))
        x_axis_label = "Log(file size)"
    else:
        mode = int(round(x_max / 1024.0, 0))
        x_axis_label = "file size, bytes"
    print(f"modal file size is {mode} KB")

    plt.title("File-size distribution and models")
    plt.xlabel(x_axis_label)
    plt.legend()
    plt.annotate(
        f"mode: {mode} KB",
        (x_max, y_max),
        textcoords="offset points",
        xytext=(-10, 0),
        ha="right",
    )
    ax.set_yticks([])
    if logspace:
        kilobyte = 1024
        ticks = np.log10(
            [
                kilobyte,
                10 * kilobyte,
                100 * kilobyte,
                kilobyte * kilobyte,
                10 * kilobyte * kilobyte,
            ]
        )
        labels = ["1 KB", "10 KB", "100 KB", "1 MB", "10 MB"]
        plt.xticks(ticks, labels)
    plt.plot(x_max, y_max, "bo", ms=10)
    if show:
        plt.show()
    else:
        plt.savefig(plot_file)


if __name__ == "__main__":
    typer.run(main)
