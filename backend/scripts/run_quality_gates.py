#!/usr/bin/env python3
"""
Quality gates for MyMetaView demo flow (2.0 / 3.0 / 3.5 / 6.0).

Run before final PR to validate:
- Regression tests pass
- Schema contracts hold
- Throughput validation logic (400% improvement measurable)
- No critical quality regressions

Usage:
  cd <project_root>
  PYTHONPATH=. python backend/scripts/run_quality_gates.py

Exit codes:
  0 - All gates passed (GO)
  1 - One or more gates failed (NO-GO)
  2 - Cannot run (missing deps, env error)
"""
import subprocess
import sys
import os
from typing import Tuple


def gate_regression_tests() -> Tuple[bool, str]:
    """Run pytest for demo flow and core tests."""
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "backend/tests/test_demo_flow.py",
                "backend/tests/test_demo_throughput.py",
                "backend/tests/test_preview_reasoning.py",
                "backend/tests/test_brand_extractor.py",
                "backend/tests/test_quality_profiles.py",
                "backend/tests/test_preview_cache_quality_policy.py",
                "-v",
                "--tb=short",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )
        if result.returncode == 0:
            return True, "Regression tests passed"
        return False, f"Regression tests failed:\n{result.stderr or result.stdout}"
    except subprocess.TimeoutExpired:
        return False, "Regression tests timed out"
    except FileNotFoundError:
        return False, "pytest not found. Install: pip install pytest"
    except Exception as e:
        return False, str(e)


def gate_schema_contracts() -> Tuple[bool, str]:
    """Validate demo schemas can be imported and basic validation works."""
    try:
        # Minimal import/validation
        from backend.schemas.demo_schemas import (
            DemoPreviewRequest,
            LayoutBlueprint,
            DemoPreviewResponse,
        )
        from backend.utils.url_sanitizer import validate_url_security

        validate_url_security("https://example.com")
        try:
            validate_url_security("file:///etc/passwd")
        except ValueError:
            pass  # expected
        else:
            return False, "URL sanitizer should reject file://"

        bp = LayoutBlueprint(
            template_type="article",
            primary_color="#2563EB",
            secondary_color="#1E40AF",
            accent_color="#F59E0B",
            coherence_score=0.85,
            balance_score=0.80,
            clarity_score=0.75,
            overall_quality="good",
            layout_reasoning="Test",
            composition_notes="Test",
        )
        assert isinstance(bp.overall_quality, str)

        req = DemoPreviewRequest(url="https://example.com")
        assert "https://example.com" in str(req.url)

        return True, "Schema contracts valid"
    except ImportError as e:
        return False, f"Schema import failed: {e}"
    except Exception as e:
        return False, str(e)


def gate_throughput_validation() -> Tuple[bool, str]:
    """Validate throughput benchmark logic and baseline (no live API)."""
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env = os.environ.copy()
        env["DEMO_BENCHMARK_SKIP_LIVE"] = "1"
        env["PYTHONPATH"] = root
        result = subprocess.run(
            [sys.executable, "backend/scripts/benchmark_demo_throughput.py", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=root,
            env=env,
        )
        if result.returncode == 0:
            return True, "Throughput validation logic OK"
        return False, f"Throughput validation failed:\n{result.stderr or result.stdout}"
    except subprocess.TimeoutExpired:
        return False, "Throughput validation timed out"
    except Exception as e:
        return False, str(e)


def main() -> int:
    """Run all quality gates."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(root)
    if "." not in sys.path:
        sys.path.insert(0, ".")

    gates = [
        ("Schema contracts", gate_schema_contracts),
        ("Regression tests", gate_regression_tests),
        ("Throughput validation", gate_throughput_validation),
    ]

    results = []
    for name, fn in gates:
        ok, msg = fn()
        results.append((name, ok, msg))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}")
        if not ok:
            print(f"  {msg}")

    failed = [r for r in results if not r[1]]
    if failed:
        print("\nNO-GO: Quality gates failed")
        return 1
    print("\nGO: All quality gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
