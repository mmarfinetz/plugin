"""Tests for screen capture module."""

import pytest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.capture.screen import Region, ScreenCapture
from src.capture.calibration import CalibrationConfig


class TestRegion:
    """Tests for Region class."""

    def test_region_creation(self):
        """Test creating a region."""
        region = Region(x=100, y=200, width=300, height=400)
        assert region.x == 100
        assert region.y == 200
        assert region.width == 300
        assert region.height == 400

    def test_region_to_dict(self):
        """Test converting region to dictionary."""
        region = Region(x=100, y=200, width=300, height=400)
        data = region.to_dict()
        assert data == {
            "x": 100,
            "y": 200,
            "width": 300,
            "height": 400,
        }

    def test_region_from_dict(self):
        """Test creating region from dictionary."""
        data = {"x": 100, "y": 200, "width": 300, "height": 400}
        region = Region.from_dict(data)
        assert region.x == 100
        assert region.y == 200
        assert region.width == 300
        assert region.height == 400

    def test_region_to_mss_monitor(self):
        """Test converting region to mss format."""
        region = Region(x=100, y=200, width=300, height=400)
        monitor = region.to_mss_monitor()
        assert monitor == {
            "left": 100,
            "top": 200,
            "width": 300,
            "height": 400,
        }


class TestCalibrationConfig:
    """Tests for CalibrationConfig class."""

    def test_config_creation(self):
        """Test creating empty config."""
        config = CalibrationConfig()
        assert config.regions == {}
        assert config.display_scale == 1.0
        assert config.game_name == ""

    def test_config_with_regions(self):
        """Test creating config with regions."""
        regions = {
            "player_cards": Region(100, 100, 200, 100),
            "dealer_cards": Region(100, 50, 200, 50),
        }
        config = CalibrationConfig(regions=regions)
        assert len(config.regions) == 2
        assert "player_cards" in config.regions
        assert "dealer_cards" in config.regions

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        regions = {
            "test_region": Region(10, 20, 30, 40),
        }
        config = CalibrationConfig(
            regions=regions,
            display_scale=2.0,
            game_name="TestGame",
        )
        data = config.to_dict()

        assert data["display_scale"] == 2.0
        assert data["game_name"] == "TestGame"
        assert "test_region" in data["regions"]
        assert data["regions"]["test_region"] == {
            "x": 10,
            "y": 20,
            "width": 30,
            "height": 40,
        }

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "display_scale": 2.0,
            "game_name": "TestGame",
            "regions": {
                "test_region": {
                    "x": 10,
                    "y": 20,
                    "width": 30,
                    "height": 40,
                },
            },
        }
        config = CalibrationConfig.from_dict(data)

        assert config.display_scale == 2.0
        assert config.game_name == "TestGame"
        assert "test_region" in config.regions
        assert config.regions["test_region"].x == 10

    def test_config_save_load(self):
        """Test saving and loading config."""
        with TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_config.json"

            # Create and save
            regions = {
                "player_cards": Region(100, 100, 200, 100),
            }
            config = CalibrationConfig(
                regions=regions,
                display_scale=2.0,
                game_name="TestGame",
            )
            config.save(filepath)

            # Load and verify
            loaded = CalibrationConfig.load(filepath)
            assert loaded.display_scale == 2.0
            assert loaded.game_name == "TestGame"
            assert "player_cards" in loaded.regions
            assert loaded.regions["player_cards"].x == 100

    def test_config_is_complete(self):
        """Test completeness check."""
        # Incomplete config
        config = CalibrationConfig()
        assert not config.is_complete()

        # Add all required regions
        from src.capture.calibration import REQUIRED_REGIONS
        for name in REQUIRED_REGIONS:
            config.regions[name] = Region(0, 0, 100, 100)

        assert config.is_complete()

    def test_config_get_missing_regions(self):
        """Test getting missing required regions."""
        config = CalibrationConfig()
        missing = config.get_missing_regions()

        from src.capture.calibration import REQUIRED_REGIONS
        assert set(missing) == set(REQUIRED_REGIONS)

    def test_config_load_not_found(self):
        """Test loading non-existent config raises error."""
        with pytest.raises(FileNotFoundError):
            CalibrationConfig.load("/nonexistent/path.json")


class TestScreenCapture:
    """Tests for ScreenCapture class.

    Note: These tests are limited because actual screen capture
    requires display access which may not be available in CI.
    """

    def test_capture_initialization(self):
        """Test capture initializes without error."""
        capture = ScreenCapture()
        assert capture._sct is None  # Lazy loaded
        capture.close()

    def test_capture_context_manager(self):
        """Test capture works as context manager."""
        with ScreenCapture() as capture:
            assert capture is not None

    def test_get_display_scale_returns_float(self):
        """Test display scale returns a float."""
        capture = ScreenCapture()
        scale = capture.get_display_scale()
        assert isinstance(scale, float)
        assert scale >= 1.0
        capture.close()

    def test_display_scale_cached(self):
        """Test display scale is cached."""
        capture = ScreenCapture()
        scale1 = capture.get_display_scale()
        scale2 = capture.get_display_scale()
        assert scale1 == scale2
        capture.close()
