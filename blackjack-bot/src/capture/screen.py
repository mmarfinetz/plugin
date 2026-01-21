"""Screen capture module for blackjack bot.

This module provides fast, low-latency screen capture functionality
using the mss library with fallback to pyautogui.
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

import mss
import mss.tools
import numpy as np
import structlog
from PIL import Image

if TYPE_CHECKING:
    from mss.base import MSSBase

logger = structlog.get_logger(__name__)


@dataclass
class Region:
    """Represents a screen region for capture.

    Attributes:
        x: Left coordinate of the region.
        y: Top coordinate of the region.
        width: Width of the region in pixels.
        height: Height of the region in pixels.
    """
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        """Convert region to dictionary format."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> Region:
        """Create region from dictionary."""
        return cls(
            x=data["x"],
            y=data["y"],
            width=data["width"],
            height=data["height"],
        )

    def to_mss_monitor(self) -> dict[str, int]:
        """Convert to mss monitor format."""
        return {
            "left": self.x,
            "top": self.y,
            "width": self.width,
            "height": self.height,
        }


class ScreenCaptureError(Exception):
    """Raised when screen capture fails."""
    pass


class ScreenCapture:
    """High-performance screen capture using mss.

    This class provides fast screen capture functionality optimized for
    real-time game state detection. It handles Retina display scaling
    on macOS automatically.

    Example:
        >>> capture = ScreenCapture()
        >>> region = Region(x=100, y=100, width=800, height=600)
        >>> frame = capture.capture_region(region)
        >>> print(frame.shape)
        (600, 800, 3)
    """

    def __init__(self) -> None:
        """Initialize screen capture with mss backend."""
        self._sct: MSSBase | None = None
        self._display_scale: float | None = None
        logger.info("ScreenCapture initialized")

    @property
    def sct(self) -> MSSBase:
        """Lazy-initialize mss instance."""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def capture_region(self, region: Region) -> np.ndarray:
        """Capture a specific region of the screen.

        Args:
            region: The screen region to capture.

        Returns:
            NumPy array of shape (height, width, 3) in BGR format
            suitable for OpenCV processing.

        Raises:
            ScreenCaptureError: If capture fails.
        """
        try:
            # Apply display scaling for Retina displays
            scale = self.get_display_scale()
            scaled_region = Region(
                x=int(region.x * scale),
                y=int(region.y * scale),
                width=int(region.width * scale),
                height=int(region.height * scale),
            )

            monitor = scaled_region.to_mss_monitor()
            screenshot = self.sct.grab(monitor)

            # Convert to numpy array (BGRA format from mss)
            img = np.array(screenshot)

            # Convert BGRA to BGR for OpenCV
            img_bgr = img[:, :, :3]

            # If scaled, resize back to expected dimensions
            if scale != 1.0:
                import cv2
                img_bgr = cv2.resize(
                    img_bgr,
                    (region.width, region.height),
                    interpolation=cv2.INTER_AREA
                )

            logger.debug(
                "captured_region",
                region=region.to_dict(),
                shape=img_bgr.shape,
            )

            return img_bgr

        except Exception as e:
            logger.error("capture_failed", error=str(e), region=region.to_dict())
            raise ScreenCaptureError(f"Failed to capture region: {e}") from e

    def capture_full_screen(self, monitor_index: int = 1) -> np.ndarray:
        """Capture the entire screen.

        Args:
            monitor_index: Index of monitor to capture (1 = primary).

        Returns:
            NumPy array of the full screen in BGR format.
        """
        try:
            monitor = self.sct.monitors[monitor_index]
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            return img[:, :, :3]  # BGRA to BGR
        except Exception as e:
            logger.error("full_screen_capture_failed", error=str(e))
            raise ScreenCaptureError(f"Failed to capture full screen: {e}") from e

    def get_display_scale(self) -> float:
        """Get the display scale factor for Retina displays.

        On macOS Retina displays, the actual pixel density is 2x the
        logical resolution. This method detects and returns the scale factor.

        Returns:
            Scale factor (1.0 for standard displays, 2.0 for Retina).
        """
        if self._display_scale is not None:
            return self._display_scale

        self._display_scale = _get_display_scale()
        logger.info("display_scale_detected", scale=self._display_scale)
        return self._display_scale

    def save_screenshot(self, region: Region, filepath: str) -> None:
        """Save a screenshot of a region to file.

        Args:
            region: The screen region to capture.
            filepath: Path to save the image (supports PNG, JPG).
        """
        img = self.capture_region(region)
        # Convert BGR to RGB for PIL
        img_rgb = img[:, :, ::-1]
        pil_image = Image.fromarray(img_rgb)
        pil_image.save(filepath)
        logger.info("screenshot_saved", filepath=filepath)

    def close(self) -> None:
        """Close the mss instance and release resources."""
        if self._sct is not None:
            self._sct.close()
            self._sct = None
            logger.info("ScreenCapture closed")

    def __enter__(self) -> ScreenCapture:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


def _get_display_scale() -> float:
    """Detect display scale factor.

    Returns:
        Scale factor for the display (1.0 for standard, 2.0 for Retina).
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        try:
            # Use system_profiler to detect Retina displays
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout.lower()

            # Check for Retina indicator
            if "retina" in output:
                return 2.0

            # Alternative: check resolution vs UI resolution
            # This is a simplified heuristic
            return 1.0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("could_not_detect_display_scale_macos")
            return 1.0

    elif system == "Windows":
        try:
            import ctypes
            # Get DPI awareness
            awareness = ctypes.windll.shcore.GetProcessDpiAwareness
            return 1.0  # Windows scaling handled differently
        except Exception:
            return 1.0

    # Linux and others default to 1.0
    return 1.0


def capture_region(region: dict[str, int]) -> np.ndarray:
    """Convenience function to capture a screen region.

    Args:
        region: Dictionary with x, y, width, height keys.

    Returns:
        NumPy array of the captured region in BGR format.

    Example:
        >>> img = capture_region({"x": 100, "y": 100, "width": 200, "height": 150})
    """
    with ScreenCapture() as capture:
        return capture.capture_region(Region.from_dict(region))


def get_display_scale() -> float:
    """Get the current display scale factor.

    Returns:
        Scale factor (1.0 for standard, 2.0 for Retina).
    """
    return _get_display_scale()
