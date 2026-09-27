# RustChain Quest #398 — Step 2: Antiquity Spoofing Fix Trace

**Known fix selected:** Antiquity Spoofing / false vintage classification  
**Pinned source:** `a4d39e9604897caf30693b05a79181018521811f`

## Before the fix

The historical failure is documented in `docs/rip201_bucket_spoof.md`. A modern x86 machine could submit contradictory identity data:

- claimed family: `PowerPC`
- claimed architecture: `G4`
- CPU brand: `Intel Xeon Platinum`

A sparse fingerprint containing only a passing anti-emulation check was sufficient for the old path. The server then treated the claim as a valid G4, enrolled it with vintage weight, and the RIP-201 bucket classifier placed it in `vintage_powerpc`.

The documented economic consequence is concrete. With one spoofed vintage participant and ten honest modern miners in a two-bucket example, the spoofed participant received 550,000 uRTC while each modern miner received 55,000 uRTC. The issue was therefore a reward-integrity bug, not merely a display mismatch.

## Current fix behavior

The current regression file `tests/test_rip201_bucket_spoof.py` captures the fixed invariants.

1. **CPU/architecture contradictions are rejected by fingerprint validation.**
   `test_validate_fingerprint_data_rejects_spoofed_g4_with_x86_cpu_brand` submits the false G4/Intel combination and requires `passed is False` with a `cpu_brand_mismatch` reason.

2. **A plausible real G4 must provide architecture-specific evidence.**
   `test_validate_fingerprint_data_accepts_verified_g4_claim` changes the CPU brand to `PowerPC G4 7447A` and supplies richer evidence including clock drift, AltiVec identity, and PowerPC cache characteristics. That claim is expected to validate.

3. **Failed vintage claims do not retain vintage identity for rewards.**
   `test_attestation_downgrades_spoofed_g4_claim_to_non_vintage_weight` requires the stored recent-attestation row to become `x86_64/default` with `fingerprint_passed=0`. The enrollment weight is 0, and the miner is not classified into `vintage_powerpc`.

4. **Public API surfaces no longer advertise the spoof as vintage.**
   The next regression requires the miner to appear as `x86_64/default`, human-readable `x86-64 (Modern)`, with the modern baseline multiplier rather than G4's vintage multiplier.

5. **Reward classification no longer creates the 10x bucket advantage.**
   `test_verified_server_side_classification_blocks_10x_reward_gain` constructs one downgraded miner plus ten modern miners and requires the spoofed miner's reward to equal an ordinary modern miner's reward.

## Why this fix is sufficient for the documented attack

For the specific historical path, the important change is not one string comparison by itself. The fix moves the economic decision away from raw client labels and toward **verified server-side classification**. The contradictory G4 claim can no longer carry its G4 identity into the enrollment/reward layer after fingerprint validation fails. That breaks the original exploit chain at the boundary that matters economically.

The regression suite also preserves a legitimate path: a real G4-like claim with architecture-specific evidence can still validate. This is important because a defense that simply rejects all vintage claims would stop the exploit by disabling the feature rather than securing it.

## Remaining security observation

The fix is sufficient for the documented Intel-as-G4 path only if all reward and bucket consumers continue to use the normalized/verified server-side architecture. Any future code path that re-reads an untrusted request field such as `device_arch` directly could reintroduce the same class of bug even if `validate_fingerprint_data()` remains correct. The regression tests are therefore valuable not only as unit tests but as an architectural invariant: failed contradictory claims must never regain vintage weight downstream.

## Reproduction status

I attempted to run the upstream targeted test command against the pinned commit:

```bash
python3 -m pytest -q tests/test_rip201_bucket_spoof.py
```

The execution environment could not resolve `github.com` while cloning the repository, so the full upstream test suite did **not** run here. I am therefore not claiming a local pytest pass. This Step 2 submission is a source-level reproduction/trace against the current pinned regression harness and historical PoC. Please score it accordingly rather than treating it as stronger evidence than it is.

## Pinned evidence

- Historical attack/fix rationale:
  https://github.com/Scottcjn/Rustchain/blob/a4d39e9604897caf30693b05a79181018521811f/docs/rip201_bucket_spoof.md
- Current regression harness:
  https://github.com/Scottcjn/Rustchain/blob/a4d39e9604897caf30693b05a79181018521811f/tests/test_rip201_bucket_spoof.py
