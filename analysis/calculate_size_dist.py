"""Make a KDE plot of file size distribution."""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


df = pd.read_csv("PDB_random_1000_sizes.tsv", sep="\t", index_col=0)
df["log10_size"] = np.log10(df["size"])
ax = sns.kdeplot(data=df["log10_size"])
x = ax.lines[0].get_xdata()  # Get the x data of the distribution
y = ax.lines[0].get_ydata()  # Get the y data of the distribution
maxid = np.argmax(y)  # The id of the peak (maximum of y data)
x_max = x[maxid]
y_max = y[maxid]
mode = int(round(10.0**x_max, 0))
print(f"modal file size is {mode}")
plt.title("KDE of file-size distribution")
plt.xlabel("log(file size, bytes)")
plt.annotate(
    f"mode: {mode}",
    (x_max, y_max),
    textcoords="offset points",
    xytext=(10, 0),
    ha="left",
)
plt.plot(x_max, y_max, "bo", ms=10)
plt.savefig("../docs/_static/file_size_distribution.svg")
