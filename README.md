# Flardl - Adaptive Multi-Site Downloading of Lists

[![PyPI](https://img.shields.io/pypi/v/flardl.svg)][pypi status]
[![Python Version](https://img.shields.io/pypi/pyversions/flardl)][pypi status]
[![Docs](https://img.shields.io/readthedocs/flardl/latest.svg?label=Read%20the%20Docs)][read the docs]
[![Tests](https://github.com/hydrationdynamics/flardl/workflows/Tests/badge.svg)][tests]
[![Codecov](https://codecov.io/gh/hydrationdynamics/flardl/branch/main/graph/badge.svg)][codecov]
[![Repo](https://img.shields.io/github/last-commit/hydrationdynamics/flardl)][repo]
[![Downloads](https://pepy.tech/badge/flardl)][downloads]
[![Dlrate](https://img.shields.io/pypi/dm/flardl)][dlrate]
[![Codacy](https://app.codacy.com/project/badge/Grade/5d86ff69c31d4f8d98ace806a21270dd)][codacy]
[![Snyk Health](https://snyk.io/advisor/python/flardl/badge.svg)][snyk]

[pypi status]: https://pypi.org/project/flardl/
[read the docs]: https://flardl.readthedocs.io/
[tests]: https://github.com/hydrationdynamics/flardl/actions?workflow=Tests
[codecov]: https://app.codecov.io/gh/hydrationdynamics/flardl
[repo]: https://github.com/hydrationdynamics/flardl
[downloads]: https://pepy.tech/project/flardl
[dlrate]: https://github.com/hydrationdynamics/flardl
[codacy]: https://www.codacy.com/gh/hydrationdynamics/flardl?utm_source=github.com&utm_medium=referral&utm_content=hydrationdynamics/zeigen&utm_campaign=Badge_Grade
[snyk]: https://snyk.io/advisor/python/flardl

> Who would flardls bear?

[![logo](https://raw.githubusercontent.com/hydrationdynamics/flardl/main/docs/_static/flardl_bear.png)][logo license]

[logo license]: https://raw.githubusercontent.com/hydrationdynamics/flardl/main/LICENSE.logo.txt

## Features

_Flardl_ uses asynchronous I/O to adaptively download a list of files from one
or more web servers. Speed advantages over synchronous downloads depends on
network bandwidth, list length, and HTTP protocol, but for a gigabit
connection using a list of 100 files, the download rate is
**more than 300X higher** than for single-file downloads. Even a single
server can saturate a gigabit connection, regardless of geographic
location, but the number of files to get to saturation varies with
latency. Use of multiple servers achieves saturated download rates on
shorter lists of files, while providing better reliability in the face
of varying upstream loads and service policies.

## Theory

Lengths of files generated by natural or human activity such as writing,
coding, protein structures, or genomes tend to more-or-less follow
**power-law distributions**, with a long tail to higher file sizes up to some maximum size
in the collection. Operations on power-law distributions are more frequently
covered in chemical rate theory than in computer-science approaches such as
the leaky-bucket algorithm of queuing theory. A full model of the downloading
process requires knowledge in advance which one doesn't generally have, such
as exact file sizes, server policies, and network loads. I aim for a model
that is both robust enough to work reliable in real situations and simple
enough to be easily coded and understood.

The nature of power-law processes is such that **mean values are nearly
worthless**, because--unlike on normal distributions--means of runs drawn
from a power-law distribution grow larger with number of samples. A few
minutes spent with a mock downloading program (such as is included in
_flardl_) will convince you that the total download time and therefore
the mean downloading rate depends strongly on how many large-size
outliers (let's call them
"[Berthas](<https://en.wikipedia.org/wiki/Big_Bertha_(howitzer)>)")
are included in your sample. Timings of algorithms that do
near-simultaneous, asynchronous downloads will also depend very much on
whether the Berthas are found at the beginning or the end of the
stream and whether or not they happen to be doled out to the same server.
A theories and algorithms based on overall times or mean rates won't
work very well on the real-world power-law collections that are most
important.

**Modal values are a good statistic for power-law distributions**, unlike
means. To put that another way, the average download time varies a lot
between runs, but the most-common download rate can be pretty
consistent. The mode of file lengths and the mode of download bit rate
are both quantities that are easy to estimate for a
collection and a collection and rarely change. If one happens to select
the biggest files for downloading, or if one happens to try downloading
a long collection at the same time that someone is watching a high-bit-rate
video on the same shared connection, then it's easy to adjust a bit
for just that time.

Even more than maximizing download rates, the highest priority must
be to **avoid black-listing by a server**. Most public-facing servers
have policies to recognize and defend against Denial-Of-Service (DOS)
attacks. The response to a DOS event, at the very least, causes the server to
dump your latest request, which is usually a minor nuisance
as it can be retried later. Far worse is
if the server responds by severely throttling further requests from your
IP address, for a period of time, generally hours or sometime days.
Worst of all, your IP address can get the "death penalty" and be put
on a permanent blacklist that may require manual intervention for
removal. You generally don't know the trigger levels for these policies.
Worse still, it might not even be you. I have seen a practical class
of 20 bioinformatics students brought to a complete halt
by a 24-hour black-listing of the institution's IP address from which
all traffic appeared to emanate by firewall policy. So, the simplest
possibility of launching a large number of requests and letting the
server sort it out is a poor strategy because it maximizes the chance
of black-listing. Given that a single server can saturate a gigabit
connection, given enough simultaneous downloads, it seems the best
strategy is to keep the request-queue depth as low as possible to
achieve that saturation. For those who are lucky enough to be on
a multi-gigabit connection, it's a good idea to limit the bandwidth
to something you know the set of servers you are using won't complain
about. It would be nice if one could query a server for an acceptable
request queue depth which would guarantee no DOS response or other
server throttling, but I have not seen such a mechanism implemented.

```{math}
:label: equation1
w_{t+1} = (1 + r_{t+1}) s(w_t) + y_{t+1}
```

See [](#equation1) for more information.

## Requirements

_Flardl_ is tested under python 3.11, on Linux, MacOS, and
Windows and under 3.9 and 3.10 on Linux. Under the hood,
_flardl_ relies on [httpx](https://www.python-httpx.org/) and is supported
on whatever platforms that library works under, for both HTTP/1.1 and HTTP/2.
HTTP/3 support could easily be added via
[aioquic](https://github.com/aiortc/aioquic) once enough servers are
running HTTP/3 to make that worthwhile.

## Installation

You can install _Flardl_ via [pip] from [PyPI]:

```console
$ pip install flardl
```

## Usage

_Flardl_ has no CLI and does no I/O other than downloading and writing
files. See test examples for usage.

## Contributing

Contributions are very welcome.
To learn more, see the [Contributor Guide].

## License

Distributed under the terms of the [BSD 3-clause_license][license],
_Flardl_ is free and open source software.

## Issues

If you encounter any problems,
please [file an issue] along with a detailed description.

## Credits

_Flardl_ was written by Joel Berendzen.

[pypi]: https://pypi.org/
[file an issue]: https://github.com/hydrationdynamics/flardl/issues
[pip]: https://pip.pypa.io/

<!-- github-only -->

[license]: https://github.com/hydrationdynamics/flardl/blob/main/LICENSE
[contributor guide]: https://github.com/hydrationdynamics/flardl/blob/main/CONTRIBUTING.md
