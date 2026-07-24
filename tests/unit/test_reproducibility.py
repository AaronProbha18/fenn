"""Tests for fenn/reproducibility.py"""

import random
import re
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from fenn.reproducibility import generate_session_id, set_seed

# ── set_seed ───────────────────────────────────────────────────────────────────


class TestSetSeed:
    def test_raises_runtime_error_without_torch(self):
        with patch.dict("sys.modules", {"torch": None}):
            with pytest.raises(RuntimeError, match="Torch is required"):
                set_seed(42)

    def test_sets_python_random_seed(self):
        set_seed(42)
        val1 = random.random()
        set_seed(42)
        val2 = random.random()
        assert val1 == val2

    def test_sets_numpy_seed(self):
        set_seed(0)
        arr1 = np.random.rand(5)
        set_seed(0)
        arr2 = np.random.rand(5)
        np.testing.assert_array_equal(arr1, arr2)

    def test_sets_torch_seed(self):
        import torch

        set_seed(7)
        t1 = torch.rand(3)
        set_seed(7)
        t2 = torch.rand(3)
        assert torch.equal(t1, t2)

    def test_different_seeds_produce_different_values(self):
        import torch

        set_seed(1)
        t1 = torch.rand(5)
        set_seed(2)
        t2 = torch.rand(5)
        assert not torch.equal(t1, t2)

    def test_sets_cudnn_deterministic(self):
        import torch

        set_seed(42)
        assert torch.backends.cudnn.deterministic is True

    def test_sets_cudnn_benchmark_false(self):
        import torch

        set_seed(42)
        assert torch.backends.cudnn.benchmark is False

    def test_cuda_seed_set_when_available(self):
        import torch

        mock_cuda = MagicMock()
        mock_cuda.is_available.return_value = True
        with patch.object(torch, "cuda", mock_cuda):
            set_seed(99)
        mock_cuda.manual_seed.assert_called_once_with(99)
        mock_cuda.manual_seed_all.assert_called_once_with(99)

    def test_cuda_seed_not_set_when_unavailable(self):
        import torch

        mock_cuda = MagicMock()
        mock_cuda.is_available.return_value = False
        with patch.object(torch, "cuda", mock_cuda):
            set_seed(99)
        mock_cuda.manual_seed.assert_not_called()
        mock_cuda.manual_seed_all.assert_not_called()

    def test_accepts_seed_zero(self):
        set_seed(0)  # should not raise

    def test_accepts_large_seed(self):
        set_seed(2**31 - 1)  # max typical seed value, should not raise


# ── generate_session_id ────────────────────────────────────────────────────────


class TestGenerateSessionId:
    def test_returns_string(self):
        assert isinstance(generate_session_id(), str)

    def test_format_matches_pattern(self):
        session_id = generate_session_id()
        # Expected: YYYYMMDD_HHMM_<4 hex chars>
        assert re.match(r"^\d{8}_\d{4}_[0-9a-f]{4}$", session_id), (
            f"Session ID '{session_id}' does not match expected format"
        )

    def test_timestamp_prefix_is_valid_date(self):
        from datetime import datetime

        session_id = generate_session_id()
        timestamp_part = "_".join(session_id.split("_")[:2])
        # Should parse as a valid datetime
        parsed = datetime.strptime(timestamp_part, "%Y%m%d_%H%M")
        assert parsed is not None

    def test_hex_suffix_is_four_chars(self):
        session_id = generate_session_id()
        hex_part = session_id.split("_")[-1]
        assert len(hex_part) == 4
        assert re.match(r"^[0-9a-f]{4}$", hex_part)

    def test_uniqueness(self):
        ids = {generate_session_id() for _ in range(50)}
        # With 2-byte hex suffix, collisions should be extremely rare
        assert len(ids) > 45

    def test_uses_secrets_for_hex(self):
        with patch(
            "fenn.reproducibility.secrets.token_hex", return_value="abcd"
        ) as mock_hex:
            session_id = generate_session_id()
        mock_hex.assert_called_once_with(2)
        assert session_id.endswith("_abcd")

    def test_timestamp_uses_current_time(self):
        from datetime import datetime

        fake_now = datetime(2024, 6, 15, 9, 30)
        with patch("fenn.reproducibility.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            session_id = generate_session_id()
        assert session_id.startswith("20240615_0930")
