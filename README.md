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

_Flardl_ adaptively downloads a list of files from a list of federated web servers.
Federated, in this case, means that one can download the same file from each server
in the list. For lists of a few hundred or more files of ~1MB in size, the download speed can
approach Gbit/s line limits, typically 300X higher than a _curl_-based script.

The main speed-up is obtained by asynchronous I/O; the use of multiple servers
provides stability and dynamic adaptability in the face of unknown server loads
and net weather.

The name _flardl_ could be either an acronym involving downloading, or a
nonsense word. You pick.

## Theory

Much has been written under the rubric of queueing theory, which we are purposefully discarding here.
We take a semi-empirical approach based around chemical rate theory; this is in many was inadequate,
but a full model of the downloading process requires prior knowledge (such as file sizes) we don't
usually possess.

The simplest version of downloading simply launches every request as quickly as possible at a
single server and lets
the server handle the queueing. The server handles overlapped responses, which quickly drives the
bandwidth to the maximum set by intervening network policy and hardware (such as ISP throttling),
where it stays until all requests are completed. However, several effects make this a bit too
simple:

- Most servers will apply a policy that dumps requests once the queue depth gets too high.
  These requests must be re-queued, and if that is done stupidly then the available
  bandwidth gets eaten with unfulfilled requests. The queue depth policy is not known
  in advance, and it may depend on total queue depth that includes other users.

- A server may decide you are executing a Denial-Of-Service (DOS) attack and respond by
  severely throttling further requests from your IP address. This throttling can last
  for hours or days, or even permanent black-listing. This "death penalty" can sometimes
  be triggered by activity of other users at the same institution that hides behind the
  same public IP address. I have seen practical classes brought to a complete halt by

## Requirements

_Flardl_ is tested under python 3.11, on Linux, MacOS, and
Windows and under 3.9 and 3.10 on Linux. Under the hood,
_flardl_ relies on
[https://www.python-httpx.org/] [httpx] and is supported
on whatever platforms that library works under, for both HTTP/1.1 and HTTP/2.
HTTP/3 support could easily be added via
[https://github.com/aiortc/aioquic][aioquic] once enough servers are
running HTTP/3 to make that worthwhile.

## Installation

You can install _Flardl_ via [pip] from [PyPI]:

```console
$ pip install flardl
```

## Usage

Please see the [Command-line Reference] for details.

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

This project was generated from [@cjolowicz]'s [Hypermodern Python Cookiecutter] template.

[@cjolowicz]: https://github.com/cjolowicz
[pypi]: https://pypi.org/
[hypermodern python cookiecutter]: https://github.com/cjolowicz/cookiecutter-hypermodern-python
[file an issue]: https://github.com/hydrationdynamics/flardl/issues
[pip]: https://pip.pypa.io/

<!-- github-only -->

[license]: https://github.com/hydrationdynamics/flardl/blob/main/LICENSE
[contributor guide]: https://github.com/hydrationdynamics/flardl/blob/main/CONTRIBUTING.md
