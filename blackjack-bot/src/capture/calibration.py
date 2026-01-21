"""Calibration tool for blackjack bot.

This module provides an interactive tool for selecting screen regions
that correspond to game elements (cards, buttons, etc.).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import structlog

from .screen import Region, ScreenCapture

logger = structlog.get_logger(__name__)


# Region types that need to be calibrated
REQUIRED_REGIONS = [
    "player_cards",
    "dealer_cards",
    "hit_button",
    "stand_button",
    "double_button",
    "split_button",
]

OPTIONAL_REGIONS = [
    "surrender_button",
    "insurance_button",
    "bet_area",
    "chip_stack",
]


@dataclass
class CalibrationConfig:
    """Configuration containing all calibrated screen regions.

    Attributes:
        regions: Dictionary mapping region names to Region objects.
        display_scale: The display scale factor when calibration was performed.
        game_name: Optional name of the game being calibrated for.
    """
    regions: dict[str, Region] = field(default_factory=dict)
    display_scale: float = 1.0
    game_name: str = ""

    def to_dict(self) -> dict:
        """Convert config to dictionary for JSON serialization."""
        return {
            "display_scale": self.display_scale,
            "game_name": self.game_name,
            "regions": {
                name: region.to_dict()
                for name, region in self.regions.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> CalibrationConfig:
        """Create config from dictionary."""
        regions = {
            name: Region.from_dict(region_data)
            for name, region_data in data.get("regions", {}).items()
        }
        return cls(
            regions=regions,
            display_scale=data.get("display_scale", 1.0),
            game_name=data.get("game_name", ""),
        )

    def save(self, filepath: str | Path) -> None:
        """Save configuration to JSON file.

        Args:
            filepath: Path to save the configuration.
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info("config_saved", filepath=str(filepath))

    @classmethod
    def load(cls, filepath: str | Path) -> CalibrationConfig:
        """Load configuration from JSON file.

        Args:
            filepath: Path to the configuration file.

        Returns:
            Loaded CalibrationConfig.

        Raises:
            FileNotFoundError: If config file doesn't exist.
        """
        filepath = Path(filepath)

        with open(filepath, "r") as f:
            data = json.load(f)

        config = cls.from_dict(data)
        logger.info("config_loaded", filepath=str(filepath))
        return config

    def is_complete(self) -> bool:
        """Check if all required regions are calibrated."""
        return all(name in self.regions for name in REQUIRED_REGIONS)

    def get_missing_regions(self) -> list[str]:
        """Get list of required regions that haven't been calibrated."""
        return [name for name in REQUIRED_REGIONS if name not in self.regions]


class CalibrationTool:
    """Interactive tool for calibrating screen regions.

    This tool allows users to select screen regions using mouse interaction
    on a captured screenshot. It supports both required and optional regions
    for complete game setup.

    Example:
        >>> tool = CalibrationTool()
        >>> config = tool.run_calibration()
        >>> config.save("config/regions.json")
    """

    def __init__(self) -> None:
        """Initialize the calibration tool."""
        self.capture = ScreenCapture()
        self.config = CalibrationConfig()
        self._current_region: str = ""
        self._selection_start: tuple[int, int] | None = None
        self._selection_end: tuple[int, int] | None = None
        self._selecting: bool = False

    def run_calibration(self, output_path: str | None = None) -> CalibrationConfig:
        """Run the interactive calibration process.

        Args:
            output_path: Optional path to save the config after calibration.

        Returns:
            Completed CalibrationConfig.
        """
        logger.info("starting_calibration")
        print("\n" + "=" * 60)
        print("BLACKJACK BOT CALIBRATION TOOL")
        print("=" * 60)
        print("\nInstructions:")
        print("1. Position your blackjack game window on screen")
        print("2. For each region, click and drag to select the area")
        print("3. Press ENTER to confirm, or 'r' to retry")
        print("4. Press 'q' at any time to quit (saving progress)")
        print("5. Press 's' to skip optional regions")
        print("\n")

        # Store display scale
        self.config.display_scale = self.capture.get_display_scale()

        # Capture full screen for reference
        screenshot = self.capture.capture_full_screen()

        # Calibrate required regions
        for region_name in REQUIRED_REGIONS:
            success = self._calibrate_region(screenshot, region_name, required=True)
            if not success:
                logger.warning("calibration_incomplete", missing=region_name)
                break

        # Calibrate optional regions
        print("\nOptional regions (press 's' to skip):")
        for region_name in OPTIONAL_REGIONS:
            success = self._calibrate_region(screenshot, region_name, required=False)
            if not success:
                # User chose to skip or quit
                continue

        cv2.destroyAllWindows()

        # Save if output path provided
        if output_path:
            self.config.save(output_path)

        logger.info(
            "calibration_complete",
            regions_calibrated=list(self.config.regions.keys()),
        )
        return self.config

    def _calibrate_region(
        self,
        screenshot: np.ndarray,
        region_name: str,
        required: bool = True,
    ) -> bool:
        """Calibrate a single region.

        Args:
            screenshot: Full screen capture.
            region_name: Name of the region to calibrate.
            required: Whether this region is required.

        Returns:
            True if region was calibrated, False if skipped/quit.
        """
        self._current_region = region_name
        self._selection_start = None
        self._selection_end = None

        # Create window for selection
        window_name = f"Select: {region_name}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        # Scale down for display if screenshot is too large
        display_scale = 1.0
        height, width = screenshot.shape[:2]
        max_display_size = 1400
        if max(height, width) > max_display_size:
            display_scale = max_display_size / max(height, width)

        display_img = cv2.resize(
            screenshot,
            None,
            fx=display_scale,
            fy=display_scale,
            interpolation=cv2.INTER_AREA,
        )

        # Set up mouse callback
        cv2.setMouseCallback(
            window_name,
            self._mouse_callback,
            {"display_scale": display_scale},
        )

        print(f"\nSelect region: {region_name}")
        if not required:
            print("  (Press 's' to skip)")

        while True:
            # Draw current selection on image
            display_copy = display_img.copy()
            if self._selection_start and self._selection_end:
                cv2.rectangle(
                    display_copy,
                    self._selection_start,
                    self._selection_end,
                    (0, 255, 0),
                    2,
                )

            cv2.imshow(window_name, display_copy)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                # Quit calibration
                cv2.destroyWindow(window_name)
                return False

            elif key == ord('s') and not required:
                # Skip optional region
                print(f"  Skipped: {region_name}")
                cv2.destroyWindow(window_name)
                return False

            elif key == ord('r'):
                # Retry selection
                self._selection_start = None
                self._selection_end = None
                print("  Selection cleared, try again...")

            elif key == 13:  # Enter key
                if self._selection_start and self._selection_end:
                    # Calculate actual region (accounting for display scale)
                    x1 = int(min(self._selection_start[0], self._selection_end[0]) / display_scale)
                    y1 = int(min(self._selection_start[1], self._selection_end[1]) / display_scale)
                    x2 = int(max(self._selection_start[0], self._selection_end[0]) / display_scale)
                    y2 = int(max(self._selection_start[1], self._selection_end[1]) / display_scale)

                    region = Region(
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    )

                    self.config.regions[region_name] = region
                    print(f"  Saved: {region_name} = {region.to_dict()}")

                    cv2.destroyWindow(window_name)
                    return True
                else:
                    print("  No selection made. Click and drag to select a region.")

        return False

    def _mouse_callback(
        self,
        event: int,
        x: int,
        y: int,
        flags: int,
        param: dict,
    ) -> None:
        """Handle mouse events for region selection."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self._selection_start = (x, y)
            self._selection_end = (x, y)
            self._selecting = True

        elif event == cv2.EVENT_MOUSEMOVE and self._selecting:
            self._selection_end = (x, y)

        elif event == cv2.EVENT_LBUTTONUP:
            self._selection_end = (x, y)
            self._selecting = False

    def calibrate_single_region(
        self,
        region_name: str,
        screenshot: np.ndarray | None = None,
    ) -> Region | None:
        """Calibrate a single region interactively.

        Args:
            region_name: Name of the region to calibrate.
            screenshot: Optional screenshot to use. If None, captures new one.

        Returns:
            The calibrated Region, or None if cancelled.
        """
        if screenshot is None:
            screenshot = self.capture.capture_full_screen()

        success = self._calibrate_region(screenshot, region_name, required=False)
        cv2.destroyAllWindows()

        if success and region_name in self.config.regions:
            return self.config.regions[region_name]
        return None

    def close(self) -> None:
        """Clean up resources."""
        self.capture.close()
        cv2.destroyAllWindows()


def run_calibration(output_path: str = "config/regions.json") -> CalibrationConfig:
    """Run the calibration tool and save results.

    This is the main entry point for calibration.

    Args:
        output_path: Path to save the calibration config.

    Returns:
        The completed CalibrationConfig.
    """
    tool = CalibrationTool()
    try:
        config = tool.run_calibration(output_path)
        return config
    finally:
        tool.close()


def load_config(filepath: str = "config/regions.json") -> CalibrationConfig:
    """Load an existing calibration configuration.

    Args:
        filepath: Path to the configuration file.

    Returns:
        Loaded CalibrationConfig.
    """
    return CalibrationConfig.load(filepath)


def validate_config(config: CalibrationConfig) -> tuple[bool, list[str]]:
    """Validate a calibration configuration.

    Args:
        config: The configuration to validate.

    Returns:
        Tuple of (is_valid, list_of_issues).
    """
    issues = []

    # Check for required regions
    missing = config.get_missing_regions()
    if missing:
        issues.append(f"Missing required regions: {missing}")

    # Check for reasonable region sizes
    for name, region in config.regions.items():
        if region.width < 10 or region.height < 10:
            issues.append(f"Region '{name}' seems too small: {region.to_dict()}")
        if region.width > 2000 or region.height > 2000:
            issues.append(f"Region '{name}' seems too large: {region.to_dict()}")

    is_valid = len(issues) == 0
    return is_valid, issues
