# Theory of Adaptilastic Queueing

The downloading process lives simultaneously in two spaces,
rates and times. In _rate space_, the observables are the
overall bandwidth in Mbit/s of all downloads, obtainable
from network interface statistics (which may
include other traffic) and the queue depth (totaled over
all server queues). In _time space_ the observables are
the download times and sizes of individual files and the
queue depth of the individual server used for the transfer.

# Quantifying download bit rates

Packets are always transmitted at full line speed, but the
number of packets transmitted per unit time are limited by
availability and policy. The effective rate is determined
by the slowest connection, typically the downstream WAN
connection. Starting transfers incurs a latency due to
handshaking, and there will also be latencies for acknowledging
receipt of data, both of which are dependent on transit times
and protocol in use. Due to these latencies, a single transfer
generally occupies only a few percent of the effective
bandwith. Packets from each subsequent concurrent transfer have
to fit into latencies of other transfers. If transfers
are occurring to a single server, simultaneously initiated,
the total bit rate versus queue depth would be approximately
an exponential relaxation to the effective network bit rate.
In practice, the approach to the effective bit rate is
complicated by different start times, different server
latencies, and possible network throttling kicking in over
time. Queue depth is not strictly defined, but time-average
queue depth can be calculated, and the relaxation to effective
bit rate is approximately a distributed exponential in that
quantity.

We wish to have an estimate to the mean value of the queue-depth
exponent to use as a limit. In principle, this is an inverse
Laplace transform, an operation notoriously numerically unstable,
even when high-quality data are available. Fits to a cooked-up
expression are also difficult and overkill, when all we wish
is a crude estimate of the sweet spot in queue depth. A simple
heuristic can be found in the analogy of chemical kinetics where
distributed rates are common. In that situation, a well-known
trick is to use the depth where the double-exponential derivative
of bit-rate versus queue depth is maximized:

$`
\begin{equation}
    D_{\rm crit} = c \overbar{D} \backepsilon
    \max{\frac{d(\log{B}}{d(\log{\overbar{D}})}}
\end{equation}
`$

where $c$ is a small constant that can be [calculated exactly][thesis]
for the case of an exponential as being near 2, close enough for
this use.

## Quantifying file transfer times

Ignoring the effects of finite packet size and treating the
networking components shared among each connection as the main
limitation to transfer rates, we can write the _Equation of Time_
for the time required to receive file $i$ from server $j$ as
approximately given by

$`
   \begin{equation}
     t_{i} = F_i - I_i \approx L_j +
        (c_{\rm ack} L_j + 1 /B_{\rm eff}) S_i +
        H_{ij}(i, D_j, D_{{\rm crit}_j})
   \end{equation}
`$

where

- $F_i$ is the finish time of the transfer,
- $I_i$ is the initial time of the transfer,
- $L_j$ is the server-dependent service latency, more-or-less
  the same as the value one gets from the _ping_ command,
- $c_{\rm ack}$ is a value reflecting the number of service latencies
  required and the number of bytes transferred per acknowledgement,
  and since it is nearly constant given the HTTP and network protocols it
  is the part of the slope expression that is fit and not measured,
- $B_{\rm eff}$ is the effective download bit rate of your WAN connection,
  which can be measured through network interface statistics if the
  transfer is long enough to reach saturation,
- $S_i$ is the size of file $i$,
- $H_{ij}$ is the file- and server-dependent
  [Head-Of-Line Latency](https://en.wikipedia.org/wiki/Head-of-line_blocking)
  that reflects waiting to get an active slot when the
  server queue depth $D_j$ is above some server-dependent
  critical value $D_{{\rm crit}_j}$.

If your downloading process is the only one accessing the server,
the Head-Of-Line latency can be quantified via the relation

$`
   \begin{equation}
     H_{ij} =
       \left\{ \begin{array}{ll}
          0, & D_j < D_{{\rm crit}_j} \cr
          I_i - F_{i^{\prime}-D_j+D_{{\rm crit}_j}-1},
           & D_j \ge D_{{\rm crit}_j} \cr
       \end{array} \right.
   \end{equation}
`$

where the prime in the subscript represents a re-indexing of
entries in order of end times rather than start times. If
other users are accessing the server at the same time, this
expression becomes indeterminate, but the important thing
to note is that it has an expectation value of a multiple
of the modal file service time, $n\tilde{t}_{\rm file}$

At queue depths small enough that no time is spent waiting to
get to the head of the line, the file transfer time is linear
in file size with the intercept given by the service
latency $L_j$ and slope governed by an expression whose only
unknown is a near-constant related to acknowledgements. As queue
depth increases, transfer times are dominated by $H_{ij}$, the
time spent waiting to get to the head of the queue.

The optimistic rate at which _flardl_ launches requests for
a given server $j$ is given by the expectation rates for
modal-sized files with small queue depths as

$`
   \begin{equation}
       k_j =
       \left\{ \begin{array}{ll}
        \tilde{S} B_{\rm max} / D_{\rm tot} & \mbox{if naive}, \\
        \tilde{\tau}_{\rm prev} B_{\rm max} / B_{\rm prev}
          & \mbox{if informed}, \\
        1/(t_{\rm cur} - I_{\rm first})
          & \mbox{if arriving,} \\
        \tilde{\tau_j} & \mbox{if updated,} \\
       \end{array} \right.
   \end{equation}
`$

where

- $\tilde{S}$ is the modal file size for the collection
  (an input parameter),
- $B_{\rm max}$ is the maximum permitted download rate
  (an input parameter),
- $D_j$ is the server queue depth at launch,
- $\tilde{\tau}_{\rm prev}$ is the modal file arrival rate
  for the previous session,
- $B_{\rm prev}$ is the saturation download bit rate for
  the previous session,
- $t_{\rm cur}$ is the current time,
- $I_{\rm first}$ is the initiation time for the first
  transfer to arrive,
- and $\tilde{\tau_j}$ is the modal file transfer rate
  for the current session with the server.

After enough files have come back from a server or set of
servers (a configurable parameter $N_{\rm min}$), _flardl_
fits the curve of observed network bandwidth versus queue
depth to obtain the effective download bit rate at saturation
$B_{\rm eff}$ and the total queue depth at saturation
$D_{\rm sat}$. Then, per-server, _flardl_ fits the curves
of service times versus file sized to the Equation of Time
to estimate server latencies $L_j$ and if the server queue
depth $D_j$ is run up high enough the critical queue depths
$`D_{{\rm crit}_j}`$. This estimates reflects local
network conditions, server policy, and overall server
load at time of request, so they are both adaptive and elastic.
These values form the bases for launching the remaining requests .
Servers with higher modal service rates (i.e., rates of serving
crappies) will spend less time waiting and thus stand a better
chance at nabbing an open queue slot, without penalizing servers
that happen to draw a big downloads (whales).

[thesis] https://www.proquest.com/openview/73b77700993c11eadd41f46f8a8f63d9/1?pq-origsite=gscholar&cbl=18750&diss=y
