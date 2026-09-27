# RustChain Quest #398 — Step 1 Security Assessment

**Claimant:** @richardfinlay5454-creator  
**Quest:** Scottcjn/rustchain-bounties#398  
**Pinned RustChain source:** `a4d39e9604897caf30693b05a79181018521811f`  
**Payout route:** hosted RustChain payout alias `richardfinlay5454-creator` pending any later native-wallet registration  
**Method:** static, non-destructive source review only  
**AI assistance disclosure:** prepared with GPT-5.6 Sol; claims were cross-checked against the pinned public source files below.

## Assessment

RustChain's security model starts with an unusual consensus premise: it replaces raw hash power with **hardware identity**, then weights eligible machines by antiquity. The protocol specification describes a five-stage cycle: the miner fingerprints its machine, submits a signed attestation to `POST /attest/submit`, the node validates the evidence, valid miners are enrolled in the current epoch, and the epoch pot is distributed by weight. The same specification fixes the epoch at 144 slots and documents a 1.5 RTC pot. This makes attestation security economically important: a mistake in classification is not merely metadata corruption; it can change reward eligibility or weight.

The public attestation documentation shows why the endpoint is a trust boundary rather than a normal registration form. A client supplies CPU/device claims plus timing, cache, SIMD, thermal, jitter, and anti-emulation evidence. The intended validation model is cross-signal: old hardware should have characteristic timing/cache/SIMD behavior, while virtual machines tend to expose cleaner clocks, flatter cache timing, hypervisor artifacts, or inconsistent architecture signals. The important security property is that the server must treat the client's labels as claims, not proof. A valid signature can establish which key sent a payload, but it does not by itself prove the physical CPU described inside that payload.

Hardware binding adds the second layer. In current `node/hardware_binding_v2.py`, a serial and architecture are hashed into a privacy-preserving binding key, while an entropy profile is extracted from clock drift, cache timing, thermal drift, and instruction jitter. New bindings require at least three non-zero comparable entropy fields. The collision scan also requires sufficiently rich profiles and runs inside the same `BEGIN IMMEDIATE` write transaction as the eventual insert. That transaction boundary matters because two first-time registrations must not both observe "no collision" and then insert separate identities for the same physical machine. Existing bindings are also wallet-bound: a different wallet is rejected, while repeat attestations compare current entropy against the stored baseline and can reject suspected spoofing or hardware swaps.

The current v2 code shows a useful fail-closed trend. New hardware with too little entropy is rejected as `entropy_insufficient`; a strong collision against another serial becomes `entropy_collision`; a different wallet on an existing serial becomes `hardware_already_bound`; and multiple stable-field mismatches can become `suspected_spoof`. This is stronger than relying on one mutable client identifier. It also highlights the design tension: entropy signals are noisy, so the implementation uses different tolerances for volatile and more stable fields. Clock CV and jitter get wide drift tolerance, while cache measurements are treated as more stable. That avoids turning normal environmental drift into a false fraud signal while still allowing stable cross-run differences to matter.

The reward side consumes the identity and enrollment state. `node/rewards_implementation_rip200.py` defines `PER_EPOCH_URTC = 1,500,000` and calculates the current epoch from 144 ten-minute slots. Settlement starts with `BEGIN IMMEDIATE`, checks whether the epoch is already settled inside that transaction, and can invoke the anti-double-mining path on the same locked connection. If that path fails while mandatory, the function returns an explicit error instead of silently dropping to the weaker path. If fallback is allowed, it rolls back, reacquires the lock, and re-checks whether another worker settled the epoch during the released-lock window before continuing. Those are important accounting controls because a consensus identity system is only as trustworthy as its final crediting path.

The standard reward branch calculates eligible rewards, credits `balances`, appends a `ledger` row, records `epoch_rewards`, derives the reporting multiplier from the attested device architecture, marks the epoch settled without replacing unrelated state, and commits. The public API exposes miner architecture and `antiquity_multiplier`, so bad classification can become externally visible and can feed economics. This is exactly why the server-side classification boundary is security-sensitive.

### Attack vector I would prioritize: architecture-class spoofing before reward classification

A concrete historical example is documented in `docs/rip201_bucket_spoof.md`: a modern Intel Xeon host could claim `device_family=PowerPC` and `device_arch=G4`, provide sparse anti-emulation evidence, and previously be accepted into a vintage reward class. The documented pre-fix effect was not cosmetic: the false G4 claim received a 2.5 multiplier and entered the `vintage_powerpc` bucket. In the example two-bucket distribution, the spoofed miner received 550,000 uRTC while each of ten honest modern miners received 55,000 uRTC — a 10x per-miner advantage.

Current regression coverage shows the intended fix direction. `tests/test_rip201_bucket_spoof.py` now requires `validate_fingerprint_data()` to reject a claimed G4 whose CPU brand is Intel, while accepting a G4 claim backed by PowerPC-specific evidence such as AltiVec and compatible cache data. A spoofed submission is retained only as a failed fingerprint, normalized to `x86_64/default`, enrolled at weight 0, excluded from the vintage bucket, and exposed by the public API as modern x86 rather than G4. The reward regression then verifies that server-side classification removes the prior vintage-bucket advantage.

The general lesson is broader than this one bug: **reward inputs must be derived from verified server-side evidence, never directly from client-declared identity strings**. Signatures, nonces, hardware binding, fingerprint validation, and settlement locking solve different parts of the problem; none substitutes for the others. The strongest design keeps these layers independent and fail-closed so that a client cannot convert one believable field into economic authority.

## Primary pinned sources

- Protocol: https://github.com/Scottcjn/Rustchain/blob/a4d39e9604897caf30693b05a79181018521811f/docs/PROTOCOL_v1.1.md
- Attestation flow: https://github.com/Scottcjn/Rustchain/blob/a4d39e9604897caf30693b05a79181018521811f/docs/attestation-flow.md
- Hardware binding v2: https://github.com/Scottcjn/Rustchain/blob/a4d39e9604897caf30693b05a79181018521811f/node/hardware_binding_v2.py
- Reward settlement: https://github.com/Scottcjn/Rustchain/blob/a4d39e9604897caf30693b05a79181018521811f/node/rewards_implementation_rip200.py
- Antiquity spoof analysis: https://github.com/Scottcjn/Rustchain/blob/a4d39e9604897caf30693b05a79181018521811f/docs/rip201_bucket_spoof.md
- Current regression: https://github.com/Scottcjn/Rustchain/blob/a4d39e9604897caf30693b05a79181018521811f/tests/test_rip201_bucket_spoof.py
