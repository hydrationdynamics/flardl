# Theory of Adaptilastic Queueing

### Quantifying rates and times

The downloading process lives simultaneously in two spaces,
rates and times. In _rate space_, the observables are the
overall bandwidth (in units of Mbit/s) of all downloads
(obtainable from network interface statistics, which may
include other traffic) and the overall queue depths at launch
and at completion. In _time space_ the observables are the
download times and sizes of individual files and the
queue depths at launch and completion of the individual
server used for the transfer.

Packets are always transmitted at line speed of the specific
connection. The effective rate is determined by the slowest
connection, typically the downstream WAN connection. Starting
transfers to a particular server requires a certain amount of
2-way exchanges for handshaking. There will also be latencies
for acknowledging receipt of packets received, depending on
the transfer protocol in use. The first transfer from a
particular server occupies only a few percent of the effective
bandwith at best. Packets from each subsequent concurrent
transfer from a server either fit into the latency periods
of other transfers or have to wait for packets to be transferred.
The total bit rate thus increases nearly linearly versus
the number of transfers for the first few concurrent transfers,
then falls off linear as more transfers interfere with each
other, then decays exponentially to zero whenever the line is
saturated with requests. The sweet spot is on the
expoentially-decaying section at the queue depth where
the decay is largest. (This may be shown analytically for
exponenential decay where the step size in queue depth
is small enough to be considered continuous.)

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

### Adaptilastic Queueing

_Flardl_ implements a method I call "adaptilastic"
queueing to deliver robust performance in real situations.
Adaptilastic queueing uses timing on transfers from an initial
period--launched using optimistic assumptions--to
optimize later transfers by using the minimum total depth over
all quese that will plateau the download bit rate while avoiding
excess queue depth on any given server. _Flardl_ distinguishes
among four different operating regimes:

- **Naive**, where no transfers have ever been completed
  on a given server,
- **Informed**, where information from a previous run
  is available,
- **Arriving**, where information from at least one transfer
  to at least one server has occurred but not enough files
  have been transferred so that all statistics can be calculated,
- **Updated**, where a sufficient number of transfers has
  occurred to a server that file transfers may be
  fully characterized.

The optimistic rate at which _flardl_ launches requests for
a given server $j$ is given by the expectation rates for
modal-sized files from the Equation of Time in the case of small
queue depths where the Head-Of-Line term is zero as

$`
   \begin{equation}
       k_j =
       \left\{ \begin{array}{ll}
        \tilde{S} B_{\rm max} / D_j & \mbox{if naive}, \\
        \tilde{\tau}_{\rm prev} B_{\rm max} / B_{\rm prev}
          & \mbox{if informed}, \\
        1/(t_{\rm cur} - I_{\rm first})
          & \mbox{if arriving,} \\
        \tilde{\tau_j} & \mbox{if updated,} \\
       \end{array} \right.
   \end{equation}
`$

where

- $\tilde{S}$ is the modal file size for the collection,
- $B_{\rm max}$ is the maximum permitted download rate,
- $D_j$ is the server queue depth at launch,
- $\tilde{\tau}_{\rm prev}$ is the modal file arrival rate
  for the previous session,
- $B_{\rm prev}$ is the plateau download bit rate for
  the previous session,
- $t_{\rm cur}$ is the current time,
- $I_{\rm first}$ is the initiation time for the first
  transfer to arrive,
- and $\tilde{\tau_j}$ is the modal file transfer rate
  for the current session.

After waiting an exponentially-distributed stochastic period
given by the applicable value for $k_j$, testing is done
against three queue depth limits:

- $D_{{\rm max}_j}$ the maximum per-server queue depth
  which is an input parameter, revised downward if any
  queue requests are rejected (default 100),
- $D_{\rm sat}$ the total queue depth at which the download
  bit rate saturates or exceeds the maximum bit rate,
- $D_{{\rm crit}_j}$ the critical per-server queue depth,
  calculated each session when updated information is available.

If any of the three queue depth limits is exceeded, a second
stochastic wait period at the inverse of the current per-server
rate $k_j$ is added.

After enough files have come back from a server or set of
servers (a configurable parameter $N_{\rm min}$), _flardl_
fits the curve of observed network bandwidth versus queue
depth to obtain the effective download bit rate at saturation
$B_{\rm eff}$ and the total queue depth at saturation
$D*{\rm sat}$. Then, per-server, _flardl_ fits the curves
of service times versus file sized to the Equation of Time
to estimate server latencies $L_j$ and if the server queue
depth $D_j$ is run up high enough the critical queue depths
$D_{{\rm crit}_j}$. This estimates reflects local
network conditions, server policy, and overall server
load at time of request, so they are both adaptive and elastic.
These values form the bases for launching the remaining requests .
Servers with higher modal service rates (i.e., rates of serving
crappies) will spend less time waiting and thus stand a better
chance at nabbing an open queue slot, without penalizing servers
that happen to draw a big downloads (whales).