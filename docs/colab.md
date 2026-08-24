# Running the experiment matrix on Colab

## The question

gprMax ships a CUDA solver behind a `-gpu` flag. The development laptop has an
AMD RX 6800M, so that solver is unreachable there and every local figure is
CPU-only. A hosted NVIDIA GPU can run it.

Confirmed before spending any time on this: the CUDA kernels do handle
multi-pole dispersive materials (`update_e_dispersive_A`, with a `MAXPOLES`
argument). Had they not, the GPU would have been useless here, since every
tissue in the model is a two-pole Debye material.

## Do not assume the GPU wins

Colab's free tier gives about **2 vCPUs** against this laptop's **16 threads**.
A CPU-only run on Colab will be several times *slower* than running locally. The
GPU is the only reason to consider it, and its speedup on this workload has not
been measured.

`notebooks/colab_gpu_benchmark.ipynb` measures it. It builds gprMax, installs
pycuda, runs the two locally-benchmarked models on both CPU and GPU, and prints
a verdict against these measured local numbers:

| workload | local throughput |
|---|---|
| benchmark model, no dispersion | 178 M cell-updates/s |
| production model, 6 Debye tissues | 74 M cell-updates/s |
| one 61-position B-scan | 610 s |
| full matrix, 192 B-scans | 32.5 h |

The number that decides it is the production model, not the benchmark - the
matrix runs dispersive tissue, and dispersion costs 2.4x locally.

About 15 minutes to run, most of it building gprMax.

## If the GPU wins

Two constraints shape how the matrix must run, regardless of speedup.

**Sessions end.** Free Colab caps a session near 12 hours and disconnects after
roughly 90 minutes idle. Even a 5x speedup leaves the matrix above 6 hours, and
a disconnect at hour 5 loses everything held only in the VM.

The matrix must therefore be split into chunks that write each B-scan to Drive
as it completes, with the driver skipping work already present. That makes the
run resumable and turns a disconnect into an inconvenience rather than a loss.
The natural chunk is one B-scan: 610 s locally, self-contained, about 165 kB as
a compressed `.npz`.

**Rebuilding costs time.** gprMax is compiled from source each session, a few
minutes every time. Caching the built tree to Drive avoids paying it repeatedly.

## What does not move

Only the FDTD solve. Geometry construction, Cole-Cole fitting, the processing
chain and the statistics all stay local, where iteration is fast, there are no
session limits, and the full 16 threads are available. Colab would be a compute
backend for one stage, not a development environment.

This is the hybrid arrangement: develop locally, solve remotely, analyse
locally.

## If the GPU does not win

Keep everything local. 32.5 hours is roughly four unattended overnight runs,
which is inconvenient but not a blocker, and it avoids all of the session
management above.
