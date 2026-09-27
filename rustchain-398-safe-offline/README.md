# RustChain #398 — Harden the Chain — Steps 1 + 2

**Claimant:** @richardfinlay5454-creator  
**Payout alias:** richardfinlay5454-creator (hosted alias if supported; native RTC address can be attached later)  
**Method:** static source review + offline local reproduction only  
**Production probing:** none  
**Pinned source commit:** `a4d39e9604897caf30693b05a79181018521811f`

## Step 1 — Security assessment

RustChain's current public protocol describes Proof-of-Antiquity as a hardware-attested reward system rather than proof-of-work. The security boundary begins before rewards are calculated: a miner gathers hardware evidence, submits a signed attestation, the node validates the evidence, and only then is the miner enrolled for an epoch. The protocol specification describes this cycle in `docs/PROTOCOL_v1.1.md` lines 11–17, while `docs/attestation-flow.md` shows the operational sequence around lines 22–29. The important security property is that a signed message proves which key submitted a claim, but it does not by itself prove that the claimed CPU architecture or physical machine is genuine. That is why the server-side fingerprint validation and hardware binding steps are the real trust boundary.

RustChain documents six anti-emulation signal classes in `docs/PROTOCOL_v1.1.md` lines 19–31: clock drift, cache timing, SIMD identity, thermal entropy, instruction jitter, and behavioral heuristics. These signals are intended to make a virtual machine or emulator distinguishable from physical silicon. This is a sensible layered design because no single user-space signal should be treated as a hardware root of trust. The security value comes from correlation: a PowerPC claim should be consistent across architecture strings, CPU brand, SIMD behavior, cache characteristics, and other measurements. The current hardware-binding implementation also compares multiple entropy fields and requires sufficient comparable non-zero evidence before treating two identities as equivalent.

The reward pipeline gives the attestation layer economic significance. `docs/PROTOCOL_v1.1.md` lines 37–47 documents antiquity multipliers, including a 2.5× multiplier for PowerPC G4 and lower weights for modern hardware. `docs/attestation-flow.md` line 43 then shows reward distribution occurring after enrollment. This means an attestation classification error is not merely cosmetic: if a modern machine can masquerade as scarce vintage hardware, the error can propagate into reward weighting and distort the one-CPU-one-vote economic model.

The attack class I consider most important is therefore **cross-field hardware identity spoofing**: client-controlled fields claim a high-value vintage architecture while the underlying evidence indicates a modern x86 host. RustChain's own historical write-up, `docs/rip201_bucket_spoof.md`, documents this exact failure mode. Around lines 13–23 it describes a claim with `device_family = PowerPC`, `device_arch = G4`, and an inconsistent `cpu = Intel Xeon Platinum`. The historical path accepted insufficiently corroborated evidence and could place the claimant into the vintage reward bucket.

The current regression suite demonstrates the fail-closed direction. In `tests/test_rip201_bucket_spoof.py`, the test beginning at line 217 requires a contradictory G4/x86 CPU claim to fail with `cpu_brand_mismatch`. The attestation-path regression later asserts that the spoofed miner's epoch enrollment weight is zero (line 274), that public API classification exposes the machine as modern x86 with a 0.8 multiplier rather than vintage G4 (line 305), and that the reward calculation no longer gives the spoofer a per-miner advantage over an honest modern miner (line 321).

The broader lesson is that RustChain should keep **claimed identity separate from verified identity**. Client-provided architecture strings should be treated as hypotheses. Reward weight and public classification should be derived from server-validated evidence, with obvious cross-field contradictions causing a fail-closed downgrade or rejection. The current regression tests encode that invariant and are valuable because they protect the economic layer from a future refactor that might accidentally re-trust raw client claims.

## Step 2 — Reproduce a known fix: Antiquity Spoofing

I chose the known **Antiquity Spoofing / vintage-bucket spoofing** class.

### Historical behavior

The public historical write-up documents a modern x86 host claiming:

- family: `PowerPC`
- architecture: `G4`
- CPU brand: `Intel Xeon Platinum`
- minimal anti-emulation evidence

Under the vulnerable policy shape, the claim could be accepted as G4 and receive the 2.5× vintage classification.

Source: `docs/rip201_bucket_spoof.md`, especially lines 13–23 and the documented reproduction/results.

### Current fix behavior

Current public regression tests require:

- contradictory G4 + x86 CPU brand → `cpu_brand_mismatch`
- `fingerprint_passed = false`
- epoch enrollment weight → `0.0`
- public classification → modern x86/default, not vintage G4
- no per-miner reward advantage versus a normal modern miner

Sources:
- `tests/test_rip201_bucket_spoof.py:217+`
- `tests/test_rip201_bucket_spoof.py:274`
- `tests/test_rip201_bucket_spoof.py:305`
- `tests/test_rip201_bucket_spoof.py:321`

### Offline reproduction

The included `offline_repro.py` is intentionally self-contained. It does **not** import the live node, send HTTP requests, access credentials, or contact rustchain.org. It models the historical policy documented by the repository and compares it with the current fail-closed invariant encoded by the regression suite.

Command:

```bash
python offline_repro.py
```

Observed output:

```text
OFFLINE_REPRO_PASS
historical_spoof_result=accepted_G4_weight_2.5
current_spoof_result=rejected_cpu_brand_mismatch_epoch_weight_0.0
control_real_G4_result=accepted_G4_weight_2.5
network_calls=0
```

The control case matters: the fixed policy does not simply reject every G4 claim. A consistent `PowerPC G4 7447A` control remains accepted at 2.5×. The security improvement is therefore specifically the rejection/downgrade of contradictory evidence, not removal of vintage rewards.

### Why the fix is sufficient for this known attack

For the demonstrated attack, the critical invariant is that **a client cannot obtain vintage reward classification merely by setting vintage architecture strings while simultaneously reporting an obviously modern x86 CPU brand**. The current regression suite enforces that invariant at validation, enrollment, public classification, and reward-calculation layers. A future bypass using subtler forged measurements would be a separate attack class and should be evaluated against the full multi-signal fingerprint validator, but the documented historical G4/Xeon spoof path is closed by the current cross-field validation and fail-closed reward behavior.

## Assistance disclosure

Prepared with AI assistance, with all factual claims checked against the pinned public repository files above. No production exploitation, live fuzzing, credential access, or destructive testing was performed.
