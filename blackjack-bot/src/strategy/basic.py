"""Basic blackjack strategy implementation.

This module provides a complete implementation of basic strategy for blackjack,
including hard totals, soft totals, and pair splitting decisions.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.vision.detector import Card

logger = structlog.get_logger(__name__)


class Action(Enum):
    """Possible blackjack actions."""
    HIT = auto()
    STAND = auto()
    DOUBLE = auto()
    SPLIT = auto()
    SURRENDER = auto()

    def __str__(self) -> str:
        return self.name


# Dealer upcard values (2-11, where 11=Ace)
# Player hand values for lookup
# Action codes: H=Hit, S=Stand, D=Double, P=Split, R=Surrender

# Hard totals strategy table
# Key: player_total, Value: dict of dealer_upcard -> action
HARD_STRATEGY: dict[int, dict[int, Action]] = {
    # Player total 5-8: Always hit
    5: {2: Action.HIT, 3: Action.HIT, 4: Action.HIT, 5: Action.HIT, 6: Action.HIT,
        7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},
    6: {2: Action.HIT, 3: Action.HIT, 4: Action.HIT, 5: Action.HIT, 6: Action.HIT,
        7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},
    7: {2: Action.HIT, 3: Action.HIT, 4: Action.HIT, 5: Action.HIT, 6: Action.HIT,
        7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},
    8: {2: Action.HIT, 3: Action.HIT, 4: Action.HIT, 5: Action.HIT, 6: Action.HIT,
        7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Player total 9: Double vs 3-6, otherwise hit
    9: {2: Action.HIT, 3: Action.DOUBLE, 4: Action.DOUBLE, 5: Action.DOUBLE, 6: Action.DOUBLE,
        7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Player total 10: Double vs 2-9, hit vs 10 and A
    10: {2: Action.DOUBLE, 3: Action.DOUBLE, 4: Action.DOUBLE, 5: Action.DOUBLE, 6: Action.DOUBLE,
         7: Action.DOUBLE, 8: Action.DOUBLE, 9: Action.DOUBLE, 10: Action.HIT, 11: Action.HIT},

    # Player total 11: Double vs all (some variations stand vs A)
    11: {2: Action.DOUBLE, 3: Action.DOUBLE, 4: Action.DOUBLE, 5: Action.DOUBLE, 6: Action.DOUBLE,
         7: Action.DOUBLE, 8: Action.DOUBLE, 9: Action.DOUBLE, 10: Action.DOUBLE, 11: Action.DOUBLE},

    # Player total 12: Stand vs 4-6, hit otherwise
    12: {2: Action.HIT, 3: Action.HIT, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Player total 13: Stand vs 2-6, hit otherwise
    13: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Player total 14: Stand vs 2-6, hit otherwise
    14: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Player total 15: Stand vs 2-6, hit vs 7-9, surrender vs 10/A (or hit if no surrender)
    15: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.SURRENDER, 11: Action.SURRENDER},

    # Player total 16: Stand vs 2-6, hit vs 7-8, surrender vs 9-A (or hit if no surrender)
    16: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.HIT, 8: Action.HIT, 9: Action.SURRENDER, 10: Action.SURRENDER, 11: Action.SURRENDER},

    # Player total 17-21: Always stand
    17: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},
    18: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},
    19: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},
    20: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},
    21: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},
}


# Soft totals strategy table
# Key: soft total (e.g., A+5=16 soft), dealer upcard -> action
SOFT_STRATEGY: dict[int, dict[int, Action]] = {
    # Soft 13 (A,2): Double vs 5-6, hit otherwise
    13: {2: Action.HIT, 3: Action.HIT, 4: Action.HIT, 5: Action.DOUBLE, 6: Action.DOUBLE,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Soft 14 (A,3): Double vs 5-6, hit otherwise
    14: {2: Action.HIT, 3: Action.HIT, 4: Action.HIT, 5: Action.DOUBLE, 6: Action.DOUBLE,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Soft 15 (A,4): Double vs 4-6, hit otherwise
    15: {2: Action.HIT, 3: Action.HIT, 4: Action.DOUBLE, 5: Action.DOUBLE, 6: Action.DOUBLE,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Soft 16 (A,5): Double vs 4-6, hit otherwise
    16: {2: Action.HIT, 3: Action.HIT, 4: Action.DOUBLE, 5: Action.DOUBLE, 6: Action.DOUBLE,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Soft 17 (A,6): Double vs 3-6, hit otherwise
    17: {2: Action.HIT, 3: Action.DOUBLE, 4: Action.DOUBLE, 5: Action.DOUBLE, 6: Action.DOUBLE,
         7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Soft 18 (A,7): Double vs 3-6, stand vs 2/7/8, hit vs 9/10/A
    18: {2: Action.STAND, 3: Action.DOUBLE, 4: Action.DOUBLE, 5: Action.DOUBLE, 6: Action.DOUBLE,
         7: Action.STAND, 8: Action.STAND, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Soft 19 (A,8): Always stand (some variations double vs 6)
    19: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},

    # Soft 20 (A,9): Always stand
    20: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},

    # Soft 21 (A,10 = Blackjack): Always stand (already 21)
    21: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},
}


# Pair splitting strategy table
# Key: pair rank value (e.g., 2 for pair of 2s), dealer upcard -> action
PAIR_STRATEGY: dict[int, dict[int, Action]] = {
    # Pair of 2s: Split vs 2-7, hit otherwise
    2: {2: Action.SPLIT, 3: Action.SPLIT, 4: Action.SPLIT, 5: Action.SPLIT, 6: Action.SPLIT,
        7: Action.SPLIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Pair of 3s: Split vs 2-7, hit otherwise
    3: {2: Action.SPLIT, 3: Action.SPLIT, 4: Action.SPLIT, 5: Action.SPLIT, 6: Action.SPLIT,
        7: Action.SPLIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Pair of 4s: Split vs 5-6 only (or hit)
    4: {2: Action.HIT, 3: Action.HIT, 4: Action.HIT, 5: Action.SPLIT, 6: Action.SPLIT,
        7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Pair of 5s: Never split (treat as 10), double vs 2-9
    5: {2: Action.DOUBLE, 3: Action.DOUBLE, 4: Action.DOUBLE, 5: Action.DOUBLE, 6: Action.DOUBLE,
        7: Action.DOUBLE, 8: Action.DOUBLE, 9: Action.DOUBLE, 10: Action.HIT, 11: Action.HIT},

    # Pair of 6s: Split vs 2-6, hit otherwise
    6: {2: Action.SPLIT, 3: Action.SPLIT, 4: Action.SPLIT, 5: Action.SPLIT, 6: Action.SPLIT,
        7: Action.HIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Pair of 7s: Split vs 2-7, hit otherwise
    7: {2: Action.SPLIT, 3: Action.SPLIT, 4: Action.SPLIT, 5: Action.SPLIT, 6: Action.SPLIT,
        7: Action.SPLIT, 8: Action.HIT, 9: Action.HIT, 10: Action.HIT, 11: Action.HIT},

    # Pair of 8s: Always split
    8: {2: Action.SPLIT, 3: Action.SPLIT, 4: Action.SPLIT, 5: Action.SPLIT, 6: Action.SPLIT,
        7: Action.SPLIT, 8: Action.SPLIT, 9: Action.SPLIT, 10: Action.SPLIT, 11: Action.SPLIT},

    # Pair of 9s: Split vs 2-6, 8-9; stand vs 7, 10, A
    9: {2: Action.SPLIT, 3: Action.SPLIT, 4: Action.SPLIT, 5: Action.SPLIT, 6: Action.SPLIT,
        7: Action.STAND, 8: Action.SPLIT, 9: Action.SPLIT, 10: Action.STAND, 11: Action.STAND},

    # Pair of 10s: Never split (stand on 20)
    10: {2: Action.STAND, 3: Action.STAND, 4: Action.STAND, 5: Action.STAND, 6: Action.STAND,
         7: Action.STAND, 8: Action.STAND, 9: Action.STAND, 10: Action.STAND, 11: Action.STAND},

    # Pair of Aces: Always split
    11: {2: Action.SPLIT, 3: Action.SPLIT, 4: Action.SPLIT, 5: Action.SPLIT, 6: Action.SPLIT,
         7: Action.SPLIT, 8: Action.SPLIT, 9: Action.SPLIT, 10: Action.SPLIT, 11: Action.SPLIT},
}


def calculate_hand_value(cards: list[Card]) -> tuple[int, bool]:
    """Calculate the blackjack value of a hand.

    Args:
        cards: List of cards in the hand.

    Returns:
        Tuple of (total_value, is_soft).
        is_soft is True if an ace is being counted as 11.
    """
    total = 0
    aces = 0

    for card in cards:
        if card.is_ace:
            aces += 1
            total += 11
        else:
            total += card.value

    # Reduce aces from 11 to 1 if busting
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    # Hand is soft if there's still an ace counted as 11
    is_soft = aces > 0 and total <= 21

    return total, is_soft


def is_soft_hand(cards: list[Card]) -> bool:
    """Check if a hand is a soft hand.

    Args:
        cards: List of cards in the hand.

    Returns:
        True if the hand contains an ace counted as 11.
    """
    _, is_soft = calculate_hand_value(cards)
    return is_soft


def is_pair(cards: list[Card]) -> bool:
    """Check if the hand is a splittable pair.

    Args:
        cards: List of cards in the hand.

    Returns:
        True if hand contains exactly two cards of the same rank.
    """
    if len(cards) != 2:
        return False

    # Compare rank values (treating all 10-value cards as same for pairs)
    val1 = min(cards[0].value, 10)
    val2 = min(cards[1].value, 10)

    # Special case: aces
    if cards[0].is_ace and cards[1].is_ace:
        return True

    return val1 == val2


def _get_dealer_value(dealer_upcard: Card) -> int:
    """Convert dealer upcard to lookup value.

    Args:
        dealer_upcard: The dealer's visible card.

    Returns:
        Integer value for strategy table lookup (2-11).
    """
    if dealer_upcard.is_ace:
        return 11
    return min(dealer_upcard.value, 10)


def _get_pair_value(cards: list[Card]) -> int:
    """Get the value for pair strategy lookup.

    Args:
        cards: The pair of cards (must be length 2).

    Returns:
        Integer value for pair strategy lookup.
    """
    if cards[0].is_ace:
        return 11
    return min(cards[0].value, 10)


def get_optimal_action(
    player_cards: list[Card],
    dealer_upcard: Card,
    can_double: bool = True,
    can_split: bool = True,
    can_surrender: bool = False,
) -> Action:
    """Determine the optimal basic strategy action.

    Args:
        player_cards: List of cards in the player's hand.
        dealer_upcard: The dealer's visible upcard.
        can_double: Whether doubling down is allowed.
        can_split: Whether splitting is allowed.
        can_surrender: Whether surrender is allowed.

    Returns:
        The optimal Action according to basic strategy.
    """
    dealer_value = _get_dealer_value(dealer_upcard)
    hand_value, is_soft = calculate_hand_value(player_cards)

    logger.debug(
        "calculating_action",
        player_cards=[str(c) for c in player_cards],
        dealer_upcard=str(dealer_upcard),
        hand_value=hand_value,
        is_soft=is_soft,
    )

    # Check for pair first (only on initial two cards)
    if can_split and is_pair(player_cards):
        pair_value = _get_pair_value(player_cards)
        action = PAIR_STRATEGY.get(pair_value, {}).get(dealer_value)

        if action:
            # If action is split, return it
            if action == Action.SPLIT:
                logger.info(
                    "action_decided",
                    action="SPLIT",
                    reason="pair_strategy",
                    pair_value=pair_value,
                )
                return Action.SPLIT

            # Otherwise fall through to handle the non-split action
            # (e.g., pair of 5s should double, not be handled as pair)

    # Soft hand strategy
    if is_soft and hand_value in SOFT_STRATEGY:
        action = SOFT_STRATEGY[hand_value].get(dealer_value, Action.HIT)

        # Handle case where double is recommended but not allowed
        if action == Action.DOUBLE and not can_double:
            # For soft hands, if can't double, generally hit
            action = Action.HIT

        logger.info(
            "action_decided",
            action=str(action),
            reason="soft_strategy",
            hand_value=hand_value,
        )
        return action

    # Hard hand strategy
    # Clamp hand value to valid range
    lookup_value = max(5, min(21, hand_value))

    if lookup_value in HARD_STRATEGY:
        action = HARD_STRATEGY[lookup_value].get(dealer_value, Action.STAND)

        # Handle case where double is recommended but not allowed
        if action == Action.DOUBLE and not can_double:
            # If can't double on 9-11, hit instead
            if hand_value <= 11:
                action = Action.HIT
            else:
                action = Action.STAND

        # Handle case where surrender is recommended but not allowed
        if action == Action.SURRENDER and not can_surrender:
            # If can't surrender, hit instead
            action = Action.HIT

        logger.info(
            "action_decided",
            action=str(action),
            reason="hard_strategy",
            hand_value=hand_value,
        )
        return action

    # Default to stand for edge cases
    logger.warning("using_default_stand", hand_value=hand_value)
    return Action.STAND


def should_take_insurance(count: int | None = None) -> bool:
    """Determine if insurance should be taken.

    Basic strategy says never take insurance. Card counters may
    take it at high counts.

    Args:
        count: Optional running count for card counting.

    Returns:
        True if insurance should be taken (almost always False).
    """
    # Basic strategy: never take insurance
    # With counting: only at true count >= +3
    if count is not None and count >= 3:
        return True
    return False


def should_take_even_money(count: int | None = None) -> bool:
    """Determine if even money should be taken on blackjack vs dealer ace.

    Basic strategy says never take even money.

    Args:
        count: Optional running count for card counting.

    Returns:
        True if even money should be taken (almost always False).
    """
    # Even money is mathematically the same as insurance
    return should_take_insurance(count)
