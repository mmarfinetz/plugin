"""Main blackjack bot orchestration.

This module provides the main bot class that coordinates screen capture,
card detection, strategy decisions, and action execution.
"""

from __future__ import annotations

import signal
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Callable

import structlog

from src.capture.calibration import CalibrationConfig, load_config
from src.capture.screen import Region, ScreenCapture
from src.vision.detector import Card, CardDetector, calculate_hand_value
from src.strategy.basic import Action, get_optimal_action
from src.automation.actions import (
    ActionExecutor,
    ClickConfig,
    FailsafeTriggered,
    RateLimiter,
)

logger = structlog.get_logger(__name__)


class BotState(Enum):
    """States of the blackjack bot."""
    IDLE = auto()
    WAITING_FOR_HAND = auto()
    ANALYZING = auto()
    DECIDING = auto()
    ACTING = auto()
    WAITING_FOR_RESULT = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()


@dataclass
class GameState:
    """Current state of the blackjack game.

    Attributes:
        player_cards: Cards in the player's hand.
        dealer_upcard: The dealer's visible card.
        hand_value: Total value of player's hand.
        is_soft: Whether the hand is soft (ace counted as 11).
        is_pair: Whether the hand is a splittable pair.
        can_double: Whether doubling is allowed.
        can_split: Whether splitting is allowed.
        can_surrender: Whether surrender is allowed.
    """
    player_cards: list[Card] = field(default_factory=list)
    dealer_upcard: Card | None = None
    hand_value: int = 0
    is_soft: bool = False
    is_pair: bool = False
    can_double: bool = True
    can_split: bool = True
    can_surrender: bool = False

    def is_valid(self) -> bool:
        """Check if game state is valid for decision making."""
        return (
            len(self.player_cards) >= 2 and
            self.dealer_upcard is not None and
            self.hand_value > 0
        )


@dataclass
class SessionStats:
    """Statistics for a bot session.

    Attributes:
        hands_played: Total hands played.
        actions_taken: Total actions executed.
        errors: Number of errors encountered.
        start_time: Session start time.
        action_counts: Count of each action type.
    """
    hands_played: int = 0
    actions_taken: int = 0
    errors: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    action_counts: dict[str, int] = field(default_factory=dict)

    def record_action(self, action: Action) -> None:
        """Record an action."""
        self.actions_taken += 1
        action_name = str(action)
        self.action_counts[action_name] = self.action_counts.get(action_name, 0) + 1

    def record_hand(self) -> None:
        """Record a completed hand."""
        self.hands_played += 1

    def record_error(self) -> None:
        """Record an error."""
        self.errors += 1

    def get_summary(self) -> dict:
        """Get session summary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            "hands_played": self.hands_played,
            "actions_taken": self.actions_taken,
            "errors": self.errors,
            "elapsed_seconds": elapsed,
            "hands_per_hour": self.hands_played / (elapsed / 3600) if elapsed > 0 else 0,
            "action_breakdown": self.action_counts,
        }


class BlackjackBot:
    """Main blackjack bot orchestrator.

    This bot coordinates all components to play blackjack automatically:
    1. Captures the game screen
    2. Detects cards using computer vision
    3. Applies basic strategy to determine optimal action
    4. Executes the action by clicking buttons

    Example:
        >>> bot = BlackjackBot("config/regions.json", dry_run=True)
        >>> bot.run()  # Start the bot loop
        >>> # Press Ctrl+C or move mouse to corner to stop
    """

    def __init__(
        self,
        config_path: str | Path,
        dry_run: bool = False,
        template_dir: str | Path = "src/vision/templates",
        on_state_change: Callable[[BotState], None] | None = None,
        on_action: Callable[[Action, GameState], None] | None = None,
    ) -> None:
        """Initialize the blackjack bot.

        Args:
            config_path: Path to calibration config file.
            dry_run: If True, simulate actions without clicking.
            template_dir: Directory containing card templates.
            on_state_change: Callback for state changes.
            on_action: Callback for actions taken.
        """
        self.config_path = Path(config_path)
        self.dry_run = dry_run
        self.template_dir = Path(template_dir)

        # Callbacks
        self.on_state_change = on_state_change
        self.on_action = on_action

        # State
        self._state = BotState.IDLE
        self._running = False
        self._paused = False
        self.stats = SessionStats()

        # Components (lazy loaded)
        self._config: CalibrationConfig | None = None
        self._capture: ScreenCapture | None = None
        self._detector: CardDetector | None = None
        self._executor: ActionExecutor | None = None
        self._rate_limiter: RateLimiter | None = None

        # Detection state
        self._last_player_cards: list[str] = []
        self._actions_this_hand: int = 0

        logger.info(
            "bot_initialized",
            config_path=str(config_path),
            dry_run=dry_run,
        )

    @property
    def state(self) -> BotState:
        """Get current bot state."""
        return self._state

    @state.setter
    def state(self, new_state: BotState) -> None:
        """Set bot state and trigger callback."""
        if new_state != self._state:
            old_state = self._state
            self._state = new_state
            logger.info("state_changed", old=str(old_state), new=str(new_state))
            if self.on_state_change:
                self.on_state_change(new_state)

    @property
    def config(self) -> CalibrationConfig:
        """Lazy-load calibration config."""
        if self._config is None:
            self._config = load_config(self.config_path)
        return self._config

    @property
    def capture(self) -> ScreenCapture:
        """Lazy-load screen capture."""
        if self._capture is None:
            self._capture = ScreenCapture()
        return self._capture

    @property
    def detector(self) -> CardDetector:
        """Lazy-load card detector."""
        if self._detector is None:
            self._detector = CardDetector(
                self.template_dir,
                confidence_threshold=0.85,
            )
        return self._detector

    @property
    def executor(self) -> ActionExecutor:
        """Lazy-load action executor."""
        if self._executor is None:
            self._executor = ActionExecutor(
                self.config,
                dry_run=self.dry_run,
                click_config=ClickConfig(
                    min_delay=0.3,
                    max_delay=0.8,
                    jitter_pixels=5,
                ),
            )
        return self._executor

    @property
    def rate_limiter(self) -> RateLimiter:
        """Lazy-load rate limiter."""
        if self._rate_limiter is None:
            self._rate_limiter = RateLimiter(
                min_interval=1.5,
                max_actions_per_minute=25,
            )
        return self._rate_limiter

    def run(self) -> None:
        """Run the main bot loop.

        This is the primary entry point that starts the bot. It will
        continuously monitor the game and take actions until stopped.

        The bot can be stopped by:
        - Pressing Ctrl+C
        - Moving the mouse to a screen corner (failsafe)
        - Calling bot.stop()
        """
        logger.info("bot_starting", dry_run=self.dry_run)
        self._running = True
        self.state = BotState.WAITING_FOR_HAND

        # Set up signal handler for graceful shutdown
        original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            while self._running:
                if self._paused:
                    self.state = BotState.PAUSED
                    time.sleep(0.5)
                    continue

                try:
                    self._game_loop_iteration()
                except FailsafeTriggered:
                    logger.warning("failsafe_triggered_stopping")
                    self.stop()
                    break
                except Exception as e:
                    logger.error("loop_error", error=str(e))
                    self.stats.record_error()
                    self.state = BotState.ERROR
                    time.sleep(2)  # Wait before retrying
                    self.state = BotState.WAITING_FOR_HAND

        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self._cleanup()

        logger.info("bot_stopped", stats=self.stats.get_summary())

    def _game_loop_iteration(self) -> None:
        """Single iteration of the game loop."""
        # Check rate limiter
        if not self.rate_limiter.can_act():
            time.sleep(0.1)
            return

        # Analyze current game state
        self.state = BotState.ANALYZING
        game_state = self._analyze_state()

        if not game_state.is_valid():
            # No valid hand detected, wait
            self.state = BotState.WAITING_FOR_HAND
            time.sleep(0.5)
            return

        # Check if this is a new hand
        current_cards = [str(c) for c in game_state.player_cards]
        if current_cards != self._last_player_cards:
            # New hand started
            if self._actions_this_hand > 0:
                self.stats.record_hand()
            self._last_player_cards = current_cards
            self._actions_this_hand = 0
            logger.info(
                "new_hand_detected",
                player_cards=current_cards,
                dealer_upcard=str(game_state.dealer_upcard),
            )

        # Check if we should act (player's turn)
        if game_state.hand_value >= 21:
            # Hand is complete (21 or bust), wait for next hand
            self.state = BotState.WAITING_FOR_RESULT
            time.sleep(1.0)
            return

        # Determine optimal action
        self.state = BotState.DECIDING
        action = self._decide_action(game_state)

        # Execute action
        self.state = BotState.ACTING
        self._execute_action(action, game_state)

        # Record stats
        self.rate_limiter.record_action()
        self.stats.record_action(action)
        self._actions_this_hand += 1

        # Update last cards if we hit
        if action == Action.HIT:
            # Cards might have changed
            time.sleep(0.5)

        # Back to waiting
        self.state = BotState.WAITING_FOR_HAND

    def _analyze_state(self) -> GameState:
        """Analyze current game state from screen.

        Returns:
            Current GameState.
        """
        game_state = GameState()

        # Capture player cards region
        player_region = self.config.regions.get("player_cards")
        if player_region:
            player_image = self.capture.capture_region(player_region)
            game_state.player_cards = self.detector.detect_player_hand(player_image)

        # Capture dealer upcard region
        dealer_region = self.config.regions.get("dealer_cards")
        if dealer_region:
            dealer_image = self.capture.capture_region(dealer_region)
            game_state.dealer_upcard = self.detector.detect_dealer_upcard(dealer_image)

        # Calculate hand value
        if game_state.player_cards:
            value, is_soft = calculate_hand_value(game_state.player_cards)
            game_state.hand_value = value
            game_state.is_soft = is_soft

            # Check if pair
            if len(game_state.player_cards) == 2:
                from src.strategy.basic import is_pair
                game_state.is_pair = is_pair(game_state.player_cards)

        # Determine available actions
        # Can double only on first two cards
        game_state.can_double = len(game_state.player_cards) == 2
        # Can split only on pairs with two cards
        game_state.can_split = game_state.is_pair
        # Surrender typically only on first two cards (if available)
        game_state.can_surrender = len(game_state.player_cards) == 2

        logger.debug(
            "game_state_analyzed",
            player_cards=[str(c) for c in game_state.player_cards],
            dealer_upcard=str(game_state.dealer_upcard) if game_state.dealer_upcard else None,
            hand_value=game_state.hand_value,
            is_soft=game_state.is_soft,
        )

        return game_state

    def _decide_action(self, game_state: GameState) -> Action:
        """Determine optimal action for current state.

        Args:
            game_state: Current game state.

        Returns:
            Optimal action according to basic strategy.
        """
        if not game_state.dealer_upcard:
            logger.warning("no_dealer_card_defaulting_to_stand")
            return Action.STAND

        action = get_optimal_action(
            player_cards=game_state.player_cards,
            dealer_upcard=game_state.dealer_upcard,
            can_double=game_state.can_double,
            can_split=game_state.can_split,
            can_surrender=game_state.can_surrender,
        )

        logger.info(
            "action_decided",
            action=str(action),
            player_cards=[str(c) for c in game_state.player_cards],
            hand_value=game_state.hand_value,
            dealer_upcard=str(game_state.dealer_upcard),
        )

        return action

    def _execute_action(self, action: Action, game_state: GameState) -> bool:
        """Execute an action.

        Args:
            action: Action to execute.
            game_state: Current game state.

        Returns:
            True if action was executed successfully.
        """
        success = self.executor.execute(action)

        if self.on_action:
            self.on_action(action, game_state)

        return success

    def _signal_handler(self, signum, frame) -> None:
        """Handle interrupt signal."""
        logger.info("interrupt_received")
        self.stop()

    def stop(self) -> None:
        """Stop the bot gracefully."""
        logger.info("stopping_bot")
        self._running = False
        self.state = BotState.STOPPED

    def pause(self) -> None:
        """Pause the bot (can be resumed)."""
        logger.info("pausing_bot")
        self._paused = True

    def resume(self) -> None:
        """Resume the bot from paused state."""
        logger.info("resuming_bot")
        self._paused = False

    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._running

    def is_paused(self) -> bool:
        """Check if bot is paused."""
        return self._paused

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self._capture:
            self._capture.close()
            self._capture = None

        self.state = BotState.STOPPED
        logger.info("bot_cleanup_complete")

    def test_detection(self) -> dict:
        """Test card detection without taking actions.

        Returns:
            Detection results.
        """
        game_state = self._analyze_state()
        return {
            "player_cards": [str(c) for c in game_state.player_cards],
            "dealer_upcard": str(game_state.dealer_upcard) if game_state.dealer_upcard else None,
            "hand_value": game_state.hand_value,
            "is_soft": game_state.is_soft,
            "is_pair": game_state.is_pair,
            "is_valid": game_state.is_valid(),
        }

    def test_strategy(self, player_cards: list[str], dealer_upcard: str) -> str:
        """Test strategy decision for given cards.

        Args:
            player_cards: List of card symbols (e.g., ["A", "7"]).
            dealer_upcard: Dealer's card symbol.

        Returns:
            Recommended action.
        """
        cards = [Card.from_string(c) for c in player_cards]
        dealer = Card.from_string(dealer_upcard)

        action = get_optimal_action(
            player_cards=cards,
            dealer_upcard=dealer,
            can_double=len(cards) == 2,
            can_split=len(cards) == 2 and cards[0].value == cards[1].value,
        )

        return str(action)


def create_bot(
    config_path: str = "config/regions.json",
    dry_run: bool = False,
    template_dir: str = "src/vision/templates",
) -> BlackjackBot:
    """Create a configured BlackjackBot instance.

    Args:
        config_path: Path to calibration config.
        dry_run: If True, simulate actions.
        template_dir: Directory containing card templates.

    Returns:
        Configured BlackjackBot.
    """
    return BlackjackBot(
        config_path=config_path,
        dry_run=dry_run,
        template_dir=template_dir,
    )
