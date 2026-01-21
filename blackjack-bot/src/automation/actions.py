"""Automation module for mouse control.

This module provides safe, human-like mouse automation for clicking
game buttons. It includes failsafe mechanisms and dry-run mode.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

import pyautogui
import structlog

from src.strategy.basic import Action
from src.capture.calibration import CalibrationConfig
from src.capture.screen import Region

logger = structlog.get_logger(__name__)


# Enable pyautogui failsafe (move mouse to corner to abort)
pyautogui.FAILSAFE = True

# Disable pyautogui pause (we'll handle our own delays)
pyautogui.PAUSE = 0


class AutomationError(Exception):
    """Raised when automation fails."""
    pass


class FailsafeTriggered(Exception):
    """Raised when the failsafe is triggered."""
    pass


@dataclass
class ClickConfig:
    """Configuration for click behavior.

    Attributes:
        min_delay: Minimum delay before click (seconds).
        max_delay: Maximum delay before click (seconds).
        click_duration: How long to hold the click (seconds).
        jitter_pixels: Random offset in pixels for click position.
        double_click_delay: Delay between double clicks (seconds).
    """
    min_delay: float = 0.3
    max_delay: float = 0.8
    click_duration: float = 0.1
    jitter_pixels: int = 3
    double_click_delay: float = 0.1


class ActionExecutor:
    """Executes blackjack actions by clicking screen buttons.

    This executor provides human-like mouse automation with built-in
    safety features including:
    - Failsafe: moving mouse to corner aborts operation
    - Dry-run mode: simulates clicks without actual input
    - Human-like delays: randomized timing between actions
    - Position jitter: small random offsets for more natural clicking

    Example:
        >>> executor = ActionExecutor(config, dry_run=True)
        >>> executor.execute(Action.HIT)
        >>> executor.execute(Action.STAND)
    """

    # Map actions to region names
    ACTION_BUTTON_MAP = {
        Action.HIT: "hit_button",
        Action.STAND: "stand_button",
        Action.DOUBLE: "double_button",
        Action.SPLIT: "split_button",
        Action.SURRENDER: "surrender_button",
    }

    def __init__(
        self,
        config: CalibrationConfig,
        dry_run: bool = False,
        click_config: ClickConfig | None = None,
        on_action: Callable[[Action, bool], None] | None = None,
    ) -> None:
        """Initialize the action executor.

        Args:
            config: Calibration config with button regions.
            dry_run: If True, simulate clicks without actual input.
            click_config: Configuration for click behavior.
            on_action: Optional callback called after each action.
        """
        self.config = config
        self.dry_run = dry_run
        self.click_config = click_config or ClickConfig()
        self.on_action = on_action
        self._last_action_time: float = 0
        self._action_count: int = 0
        self._enabled: bool = True

        logger.info(
            "action_executor_initialized",
            dry_run=dry_run,
            regions=list(config.regions.keys()),
        )

    def execute(self, action: Action) -> bool:
        """Execute a blackjack action by clicking the appropriate button.

        Args:
            action: The action to execute.

        Returns:
            True if action was executed successfully.

        Raises:
            FailsafeTriggered: If mouse is moved to corner.
            AutomationError: If action cannot be executed.
        """
        if not self._enabled:
            logger.warning("executor_disabled", action=str(action))
            return False

        # Get button region for this action
        button_name = self.ACTION_BUTTON_MAP.get(action)
        if not button_name:
            logger.error("unknown_action", action=str(action))
            return False

        region = self.config.regions.get(button_name)
        if not region:
            logger.error(
                "button_not_calibrated",
                action=str(action),
                button=button_name,
            )
            raise AutomationError(f"Button not calibrated: {button_name}")

        # Calculate click position (center of region with jitter)
        x, y = self._calculate_click_position(region)

        # Add human-like delay
        self._human_delay()

        # Execute click
        success = self._click(x, y)

        # Track action
        self._last_action_time = time.time()
        self._action_count += 1

        # Callback
        if self.on_action:
            self.on_action(action, success)

        logger.info(
            "action_executed",
            action=str(action),
            position=(x, y),
            dry_run=self.dry_run,
            success=success,
        )

        return success

    def _calculate_click_position(self, region: Region) -> tuple[int, int]:
        """Calculate click position with jitter.

        Args:
            region: The button region.

        Returns:
            (x, y) coordinates for the click.
        """
        # Center of region
        center_x = region.x + region.width // 2
        center_y = region.y + region.height // 2

        # Add random jitter
        jitter = self.click_config.jitter_pixels
        x = center_x + random.randint(-jitter, jitter)
        y = center_y + random.randint(-jitter, jitter)

        return x, y

    def _human_delay(self) -> None:
        """Add a human-like delay before action."""
        delay = random.uniform(
            self.click_config.min_delay,
            self.click_config.max_delay,
        )

        # Add extra delay if clicking rapidly
        time_since_last = time.time() - self._last_action_time
        if time_since_last < 0.5:
            delay += random.uniform(0.1, 0.3)

        logger.debug("human_delay", delay_seconds=delay)
        time.sleep(delay)

    def _click(self, x: int, y: int) -> bool:
        """Perform a mouse click.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if click was performed.

        Raises:
            FailsafeTriggered: If failsafe is triggered.
        """
        try:
            if self.dry_run:
                logger.debug("dry_run_click", x=x, y=y)
                return True

            # Check failsafe before clicking
            self._check_failsafe()

            # Move to position with human-like movement
            pyautogui.moveTo(
                x, y,
                duration=random.uniform(0.1, 0.25),
            )

            # Small pause after move
            time.sleep(random.uniform(0.02, 0.08))

            # Check failsafe again
            self._check_failsafe()

            # Click
            pyautogui.click(
                clicks=1,
                interval=self.click_config.double_click_delay,
            )

            return True

        except pyautogui.FailSafeException:
            logger.warning("failsafe_triggered_pyautogui")
            raise FailsafeTriggered("Mouse moved to corner - operation aborted")

    def _check_failsafe(self) -> None:
        """Check if mouse is in failsafe corner.

        Raises:
            FailsafeTriggered: If mouse is in failsafe position.
        """
        x, y = pyautogui.position()
        screen_width, screen_height = pyautogui.size()

        # Check corners (within 10 pixels)
        corner_threshold = 10
        in_corner = (
            (x <= corner_threshold and y <= corner_threshold) or  # Top-left
            (x >= screen_width - corner_threshold and y <= corner_threshold) or  # Top-right
            (x <= corner_threshold and y >= screen_height - corner_threshold) or  # Bottom-left
            (x >= screen_width - corner_threshold and y >= screen_height - corner_threshold)  # Bottom-right
        )

        if in_corner:
            raise FailsafeTriggered("Mouse in corner - failsafe triggered")

    def click_region(self, region_name: str) -> bool:
        """Click a specific calibrated region.

        Args:
            region_name: Name of the region to click.

        Returns:
            True if click was performed.
        """
        region = self.config.regions.get(region_name)
        if not region:
            logger.error("region_not_found", region=region_name)
            return False

        x, y = self._calculate_click_position(region)
        self._human_delay()
        return self._click(x, y)

    def click_position(self, x: int, y: int) -> bool:
        """Click a specific screen position.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if click was performed.
        """
        self._human_delay()
        return self._click(x, y)

    def enable(self) -> None:
        """Enable the executor."""
        self._enabled = True
        logger.info("executor_enabled")

    def disable(self) -> None:
        """Disable the executor (no actions will be executed)."""
        self._enabled = False
        logger.info("executor_disabled")

    def is_enabled(self) -> bool:
        """Check if executor is enabled."""
        return self._enabled

    def get_stats(self) -> dict:
        """Get execution statistics.

        Returns:
            Dictionary with execution stats.
        """
        return {
            "total_actions": self._action_count,
            "last_action_time": self._last_action_time,
            "enabled": self._enabled,
            "dry_run": self.dry_run,
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._action_count = 0
        self._last_action_time = 0


class RateLimiter:
    """Rate limiter to prevent too-rapid actions.

    This helps avoid detection and ensures human-like pacing.
    """

    def __init__(
        self,
        min_interval: float = 1.0,
        max_actions_per_minute: int = 30,
    ) -> None:
        """Initialize rate limiter.

        Args:
            min_interval: Minimum seconds between actions.
            max_actions_per_minute: Maximum actions allowed per minute.
        """
        self.min_interval = min_interval
        self.max_actions_per_minute = max_actions_per_minute
        self._action_times: list[float] = []
        self._last_action: float = 0

    def can_act(self) -> bool:
        """Check if an action is allowed now.

        Returns:
            True if action is allowed.
        """
        now = time.time()

        # Check minimum interval
        if now - self._last_action < self.min_interval:
            return False

        # Clean old entries (older than 1 minute)
        self._action_times = [t for t in self._action_times if now - t < 60]

        # Check rate limit
        if len(self._action_times) >= self.max_actions_per_minute:
            return False

        return True

    def record_action(self) -> None:
        """Record that an action was taken."""
        now = time.time()
        self._action_times.append(now)
        self._last_action = now

    def wait_until_allowed(self) -> float:
        """Wait until an action is allowed.

        Returns:
            Seconds waited.
        """
        waited = 0.0

        while not self.can_act():
            sleep_time = 0.1
            time.sleep(sleep_time)
            waited += sleep_time

        return waited


def create_executor(
    config_path: str,
    dry_run: bool = False,
) -> ActionExecutor:
    """Create an ActionExecutor from a config file.

    Args:
        config_path: Path to the calibration config.
        dry_run: If True, simulate clicks.

    Returns:
        Configured ActionExecutor.
    """
    from src.capture.calibration import CalibrationConfig

    config = CalibrationConfig.load(config_path)
    return ActionExecutor(config, dry_run=dry_run)
