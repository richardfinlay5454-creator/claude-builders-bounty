"""Offline defensive reproduction for RustChain bounty #398 Step 2.

No network calls are made. This models the historical antiquity-spoofing
policy documented in Scottcjn/Rustchain and checks the current fail-closed
invariant represented by tests/test_rip201_bucket_spoof.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Claim:
    device_family: str
    device_arch: str
    cpu_brand: str
    anti_emulation_passed: bool


VINTAGE_MULTIPLIERS = {"G3": 1.8, "G4": 2.5, "G5": 2.0}
MODERN_X86_MULTIPLIER = 0.8


def vulnerable_policy(claim: Claim):
    if not claim.anti_emulation_passed:
        return {"fingerprint_passed": False, "arch": "default", "weight": 0.0}
    if claim.device_family == "PowerPC" and claim.device_arch in VINTAGE_MULTIPLIERS:
        return {
            "fingerprint_passed": True,
            "arch": claim.device_arch,
            "weight": VINTAGE_MULTIPLIERS[claim.device_arch],
        }
    return {
        "fingerprint_passed": True,
        "arch": "default",
        "weight": MODERN_X86_MULTIPLIER,
    }


def fixed_policy(claim: Claim):
    brand = claim.cpu_brand.lower()
    claims_powerpc = (
        claim.device_family.lower() == "powerpc"
        or claim.device_arch.lower() in {"g3", "g4", "g5"}
    )
    obvious_x86 = any(
        token in brand for token in ("intel", "xeon", "amd", "ryzen", "x86")
    )

    if claims_powerpc and obvious_x86:
        return {
            "fingerprint_passed": False,
            "arch": "default",
            "public_multiplier": MODERN_X86_MULTIPLIER,
            "epoch_weight": 0.0,
            "reason": "cpu_brand_mismatch",
        }

    if not claim.anti_emulation_passed:
        return {
            "fingerprint_passed": False,
            "arch": "default",
            "public_multiplier": MODERN_X86_MULTIPLIER,
            "epoch_weight": 0.0,
            "reason": "anti_emulation_failed",
        }

    weight = VINTAGE_MULTIPLIERS.get(
        claim.device_arch, MODERN_X86_MULTIPLIER
    )
    return {
        "fingerprint_passed": True,
        "arch": claim.device_arch,
        "public_multiplier": weight,
        "epoch_weight": weight,
        "reason": "valid",
    }


def main():
    spoof = Claim(
        device_family="PowerPC",
        device_arch="G4",
        cpu_brand="Intel Xeon Platinum",
        anti_emulation_passed=True,
    )
    real_g4 = Claim(
        device_family="PowerPC",
        device_arch="G4",
        cpu_brand="PowerPC G4 7447A",
        anti_emulation_passed=True,
    )

    before = vulnerable_policy(spoof)
    after = fixed_policy(spoof)
    control = fixed_policy(real_g4)

    assert before == {
        "fingerprint_passed": True,
        "arch": "G4",
        "weight": 2.5,
    }
    assert after["fingerprint_passed"] is False
    assert after["arch"] == "default"
    assert after["epoch_weight"] == 0.0
    assert after["reason"] == "cpu_brand_mismatch"

    assert control["fingerprint_passed"] is True
    assert control["arch"] == "G4"
    assert control["epoch_weight"] == 2.5

    print("OFFLINE_REPRO_PASS")
    print("historical_spoof_result=accepted_G4_weight_2.5")
    print("current_spoof_result=rejected_cpu_brand_mismatch_epoch_weight_0.0")
    print("control_real_G4_result=accepted_G4_weight_2.5")
    print("network_calls=0")


if __name__ == "__main__":
    main()
