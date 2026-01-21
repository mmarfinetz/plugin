"""Comprehensive tests for basic strategy implementation.

This test suite covers all basic strategy decisions to ensure
the bot plays optimally according to standard basic strategy.
"""

import pytest

from src.strategy.basic import (
    Action,
    calculate_hand_value,
    get_optimal_action,
    is_pair,
    is_soft_hand,
    HARD_STRATEGY,
    SOFT_STRATEGY,
    PAIR_STRATEGY,
)
from src.vision.detector import Card, Rank, Suit


def make_card(rank_str: str, suit: str = "spades") -> Card:
    """Helper to create cards for testing."""
    return Card.from_string(rank_str, suit)


def make_hand(*ranks: str) -> list[Card]:
    """Helper to create a hand from rank strings."""
    return [make_card(r) for r in ranks]


class TestHandValue:
    """Tests for hand value calculation."""

    def test_simple_hard_hand(self):
        """Test simple hard hand values."""
        hand = make_hand("10", "6")
        value, is_soft = calculate_hand_value(hand)
        assert value == 16
        assert not is_soft

    def test_soft_hand_with_ace(self):
        """Test soft hand with single ace."""
        hand = make_hand("A", "7")
        value, is_soft = calculate_hand_value(hand)
        assert value == 18
        assert is_soft

    def test_hard_hand_with_ace(self):
        """Test hand where ace must be 1 to avoid bust."""
        hand = make_hand("A", "7", "6")
        value, is_soft = calculate_hand_value(hand)
        assert value == 14
        assert not is_soft

    def test_multiple_aces(self):
        """Test hand with multiple aces."""
        hand = make_hand("A", "A")
        value, is_soft = calculate_hand_value(hand)
        assert value == 12
        assert is_soft

    def test_blackjack(self):
        """Test blackjack hand."""
        hand = make_hand("A", "K")
        value, is_soft = calculate_hand_value(hand)
        assert value == 21
        assert is_soft

    def test_bust_hand(self):
        """Test busted hand."""
        hand = make_hand("10", "7", "8")
        value, is_soft = calculate_hand_value(hand)
        assert value == 25
        assert not is_soft

    def test_three_aces(self):
        """Test hand with three aces."""
        hand = make_hand("A", "A", "A")
        value, is_soft = calculate_hand_value(hand)
        assert value == 13
        assert is_soft


class TestIsPair:
    """Tests for pair detection."""

    def test_pair_of_eights(self):
        """Test pair of 8s."""
        hand = make_hand("8", "8")
        assert is_pair(hand)

    def test_pair_of_aces(self):
        """Test pair of aces."""
        hand = make_hand("A", "A")
        assert is_pair(hand)

    def test_pair_of_tens(self):
        """Test pair of 10-value cards (different ranks)."""
        hand = make_hand("10", "K")
        assert is_pair(hand)  # Both are 10 value

    def test_not_pair_different_ranks(self):
        """Test non-pair hand."""
        hand = make_hand("8", "9")
        assert not is_pair(hand)

    def test_not_pair_three_cards(self):
        """Test three cards (not a pair for splitting)."""
        hand = make_hand("8", "8", "2")
        assert not is_pair(hand)


class TestIsSoftHand:
    """Tests for soft hand detection."""

    def test_soft_17(self):
        """Test soft 17."""
        hand = make_hand("A", "6")
        assert is_soft_hand(hand)

    def test_hard_17(self):
        """Test hard 17."""
        hand = make_hand("10", "7")
        assert not is_soft_hand(hand)

    def test_becomes_hard(self):
        """Test hand that starts soft but becomes hard."""
        hand = make_hand("A", "6", "10")
        assert not is_soft_hand(hand)


class TestHardTotals:
    """Tests for hard total strategy decisions."""

    @pytest.mark.parametrize("total,dealer,expected", [
        # Always hit on 8 or less
        (8, 6, Action.HIT),
        (7, 5, Action.HIT),

        # Double on 9 vs 3-6
        (9, 3, Action.DOUBLE),
        (9, 6, Action.DOUBLE),
        (9, 2, Action.HIT),
        (9, 7, Action.HIT),

        # Double on 10 vs 2-9
        (10, 2, Action.DOUBLE),
        (10, 9, Action.DOUBLE),
        (10, 10, Action.HIT),
        (10, 11, Action.HIT),

        # Double on 11 vs all
        (11, 2, Action.DOUBLE),
        (11, 10, Action.DOUBLE),
        (11, 11, Action.DOUBLE),

        # Stand on 12 vs 4-6
        (12, 4, Action.STAND),
        (12, 6, Action.STAND),
        (12, 2, Action.HIT),
        (12, 7, Action.HIT),

        # Stand on 13-16 vs 2-6
        (13, 2, Action.STAND),
        (14, 6, Action.STAND),
        (15, 5, Action.STAND),
        (16, 3, Action.STAND),

        # Hit on 13-16 vs 7+
        (13, 7, Action.HIT),
        (14, 8, Action.HIT),
        (15, 9, Action.HIT),
        (16, 7, Action.HIT),

        # Always stand on 17+
        (17, 10, Action.STAND),
        (18, 11, Action.STAND),
        (19, 2, Action.STAND),
        (20, 5, Action.STAND),
    ])
    def test_hard_strategy(self, total, dealer, expected):
        """Test hard total strategy decisions."""
        # Build a hand that equals the total
        if total <= 10:
            hand = make_hand(str(total))
        else:
            hand = make_hand("10", str(total - 10))

        dealer_card = make_card("A" if dealer == 11 else str(dealer))

        # For doubles, test both with and without double available
        result = get_optimal_action(hand, dealer_card, can_double=True)
        assert result == expected

    def test_hard_16_vs_10_hit(self):
        """Player 10,6 vs dealer 10 should HIT."""
        hand = make_hand("10", "6")
        dealer = make_card("10")
        assert get_optimal_action(hand, dealer) == Action.HIT

    def test_hard_16_vs_10_surrender_when_available(self):
        """Player 10,6 vs dealer 10 should SURRENDER if available."""
        hand = make_hand("10", "6")
        dealer = make_card("10")
        result = get_optimal_action(hand, dealer, can_surrender=True)
        assert result == Action.SURRENDER


class TestSoftTotals:
    """Tests for soft total strategy decisions."""

    @pytest.mark.parametrize("hand_cards,dealer,expected", [
        # Soft 13 (A,2): Double vs 5-6, hit otherwise
        (["A", "2"], "5", Action.DOUBLE),
        (["A", "2"], "6", Action.DOUBLE),
        (["A", "2"], "4", Action.HIT),
        (["A", "2"], "7", Action.HIT),

        # Soft 14 (A,3): Double vs 5-6, hit otherwise
        (["A", "3"], "5", Action.DOUBLE),
        (["A", "3"], "4", Action.HIT),

        # Soft 15 (A,4): Double vs 4-6, hit otherwise
        (["A", "4"], "4", Action.DOUBLE),
        (["A", "4"], "3", Action.HIT),

        # Soft 16 (A,5): Double vs 4-6, hit otherwise
        (["A", "5"], "4", Action.DOUBLE),
        (["A", "5"], "7", Action.HIT),

        # Soft 17 (A,6): Double vs 3-6, hit otherwise
        (["A", "6"], "3", Action.DOUBLE),
        (["A", "6"], "2", Action.HIT),
        (["A", "6"], "7", Action.HIT),

        # Soft 18 (A,7): Double vs 3-6, stand vs 2/7/8, hit vs 9/10/A
        (["A", "7"], "3", Action.DOUBLE),
        (["A", "7"], "2", Action.STAND),
        (["A", "7"], "7", Action.STAND),
        (["A", "7"], "8", Action.STAND),
        (["A", "7"], "9", Action.HIT),
        (["A", "7"], "10", Action.HIT),
        (["A", "7"], "A", Action.HIT),

        # Soft 19 (A,8): Always stand
        (["A", "8"], "6", Action.STAND),
        (["A", "8"], "10", Action.STAND),

        # Soft 20 (A,9): Always stand
        (["A", "9"], "6", Action.STAND),
    ])
    def test_soft_strategy(self, hand_cards, dealer, expected):
        """Test soft total strategy decisions."""
        hand = make_hand(*hand_cards)
        dealer_card = make_card(dealer)
        result = get_optimal_action(hand, dealer_card, can_double=True)
        assert result == expected

    def test_soft_double_fallback_to_hit(self):
        """Test soft hand double falls back to hit when can't double."""
        hand = make_hand("A", "6")  # Soft 17
        dealer = make_card("4")  # Should double
        result = get_optimal_action(hand, dealer, can_double=False)
        assert result == Action.HIT


class TestPairSplitting:
    """Tests for pair splitting strategy decisions."""

    def test_pair_aces_always_split(self):
        """Pair of aces should always split."""
        hand = make_hand("A", "A")
        for dealer_rank in ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"]:
            dealer = make_card(dealer_rank)
            result = get_optimal_action(hand, dealer, can_split=True)
            assert result == Action.SPLIT, f"Aces vs {dealer_rank} should split"

    def test_pair_eights_always_split(self):
        """Pair of 8s should always split."""
        hand = make_hand("8", "8")
        for dealer_rank in ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"]:
            dealer = make_card(dealer_rank)
            result = get_optimal_action(hand, dealer, can_split=True)
            assert result == Action.SPLIT, f"8s vs {dealer_rank} should split"

    def test_pair_tens_never_split(self):
        """Pair of 10s should never split (stand on 20)."""
        hand = make_hand("10", "10")
        for dealer_rank in ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"]:
            dealer = make_card(dealer_rank)
            result = get_optimal_action(hand, dealer, can_split=True)
            assert result == Action.STAND, f"10s vs {dealer_rank} should stand"

    def test_pair_fives_never_split(self):
        """Pair of 5s should never split (double as 10)."""
        hand = make_hand("5", "5")
        dealer = make_card("6")
        result = get_optimal_action(hand, dealer, can_split=True, can_double=True)
        assert result == Action.DOUBLE

    @pytest.mark.parametrize("pair,dealer,expected", [
        # 2s: Split vs 2-7
        ("2", "2", Action.SPLIT),
        ("2", "7", Action.SPLIT),
        ("2", "8", Action.HIT),

        # 3s: Split vs 2-7
        ("3", "2", Action.SPLIT),
        ("3", "7", Action.SPLIT),
        ("3", "8", Action.HIT),

        # 4s: Split vs 5-6 only
        ("4", "5", Action.SPLIT),
        ("4", "6", Action.SPLIT),
        ("4", "4", Action.HIT),
        ("4", "7", Action.HIT),

        # 6s: Split vs 2-6
        ("6", "2", Action.SPLIT),
        ("6", "6", Action.SPLIT),
        ("6", "7", Action.HIT),

        # 7s: Split vs 2-7
        ("7", "2", Action.SPLIT),
        ("7", "7", Action.SPLIT),
        ("7", "8", Action.HIT),

        # 9s: Split vs 2-6, 8-9; stand vs 7, 10, A
        ("9", "2", Action.SPLIT),
        ("9", "6", Action.SPLIT),
        ("9", "7", Action.STAND),
        ("9", "8", Action.SPLIT),
        ("9", "9", Action.SPLIT),
        ("9", "10", Action.STAND),
        ("9", "A", Action.STAND),
    ])
    def test_pair_splitting(self, pair, dealer, expected):
        """Test pair splitting decisions."""
        hand = make_hand(pair, pair)
        dealer_card = make_card(dealer)
        result = get_optimal_action(hand, dealer_card, can_split=True)
        assert result == expected


class TestEdgeCases:
    """Tests for edge cases and special situations."""

    def test_cant_double_fallback(self):
        """Test fallback when doubling not allowed."""
        hand = make_hand("6", "5")  # 11
        dealer = make_card("6")
        # With double
        assert get_optimal_action(hand, dealer, can_double=True) == Action.DOUBLE
        # Without double
        assert get_optimal_action(hand, dealer, can_double=False) == Action.HIT

    def test_cant_split_fallback(self):
        """Test fallback when splitting not allowed."""
        hand = make_hand("8", "8")  # Pair
        dealer = make_card("6")
        # Without split, treat as 16
        result = get_optimal_action(hand, dealer, can_split=False)
        # 16 vs 6 should stand
        assert result == Action.STAND

    def test_surrender_fallback(self):
        """Test fallback when surrender not allowed."""
        hand = make_hand("10", "6")  # 16
        dealer = make_card("10")
        # With surrender
        assert get_optimal_action(hand, dealer, can_surrender=True) == Action.SURRENDER
        # Without surrender
        assert get_optimal_action(hand, dealer, can_surrender=False) == Action.HIT

    def test_three_card_hand_no_double(self):
        """Test that three-card hands correctly don't allow doubling."""
        hand = make_hand("4", "3", "4")  # 11
        dealer = make_card("6")
        # Even though 11, can't double after hit
        result = get_optimal_action(hand, dealer, can_double=False)
        assert result == Action.HIT

    def test_blackjack_stand(self):
        """Test that blackjack stands."""
        hand = make_hand("A", "K")
        dealer = make_card("6")
        assert get_optimal_action(hand, dealer) == Action.STAND


class TestStrategyTables:
    """Tests to verify strategy tables are complete."""

    def test_hard_strategy_complete(self):
        """Verify hard strategy covers all totals."""
        for total in range(5, 22):
            assert total in HARD_STRATEGY
            for dealer in range(2, 12):
                assert dealer in HARD_STRATEGY[total]

    def test_soft_strategy_complete(self):
        """Verify soft strategy covers all soft totals."""
        for total in range(13, 22):
            assert total in SOFT_STRATEGY
            for dealer in range(2, 12):
                assert dealer in SOFT_STRATEGY[total]

    def test_pair_strategy_complete(self):
        """Verify pair strategy covers all pairs."""
        for pair in range(2, 12):  # 2-10, 11=Ace
            assert pair in PAIR_STRATEGY
            for dealer in range(2, 12):
                assert dealer in PAIR_STRATEGY[pair]
