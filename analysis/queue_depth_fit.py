#!/usr/bin/env python
"""Make a KDE plot of file size distribution."""
from pathlib import Path
from typing import Annotated
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import typer


DEFAULT_NPOINTS = 1000
D_CRIT = 100.
FRACTIONAL_CUTOFF = 0.7
B_EFF = 1.
DOWNSCALE_RANGE = 10.


def main(
    plot_file: Annotated[Optional[Path], typer.Option()] = None,
    npoints: int = DEFAULT_NPOINTS,
    show: bool = False,
):
    """Plot exponential distribution in log-log space, with derivative."""
    D = np.arange(1, npoints+1, 1)
    B = B_EFF*(1.-np.exp(-1.*D/D_CRIT))
    logB = np.log10(B)
    logD = np.log10(D)
    max_B = logB.max()
    initial_pts = np.where(logB < max_B-FRACTIONAL_CUTOFF)[0]
    print("initial_pts", len(initial_pts))
    plt.rcParams.update({"font.size": 14})
    plt.rcParams["text.usetex"] = True
    plt.plot(
        logD,
        logB,
        linewidth=2,
        label="exponential",
    )
    slope, intercept = np.polyfit(logD[initial_pts], logB[initial_pts], deg=1)
    fit = intercept + slope * logD
    crit = int(round(10.**(max_B - intercept)/slope, 0))
    print(f"max: {max_B}, slope: {slope}, intercept: {intercept}, crit: {crit}")
    plt.plot(
        logD,
        fit,
        linewidth=2,
        linestyle="dashed",
        label="derivative",
    )
    plt.title("Saturation of Bandwidth")
    plt.xlabel(r"Queue Depth")
    plt.ylabel("Bandwidth/B_{eff}")
    plt.legend()
    #plt.annotate(
    #    f"mode: {mode} KB",
    #    (x_max, y_max),
    #    textcoords="offset points",
    #   xytext=(-10, 0),
    #   ha="right",
    #
    #plt.plot(x_max, y_max, "bo", ms=10)
    if show:
        plt.show()
    else:
        plt.savefig(plot_file)


if __name__ == "__main__":
    typer.run(main)
