"""Tests for card detection module."""

import pytest
import numpy as np

from src.vision.detector import (
    Card,
    Rank,
    Suit,
    Match,
    CardDetector,
    calculate_hand_value,
)


class TestCard:
    """Tests for Card class."""

    def test_card_creation(self):
        """Test creating a card."""
        card = Card(rank=Rank.ACE, suit=Suit.SPADES)
        assert card.rank == Rank.ACE
        assert card.suit == Suit.SPADES

    def test_card_from_string(self):
        """Test creating card from string."""
        card = Card.from_string("A", "hearts")
        assert card.rank == Rank.ACE
        assert card.suit == Suit.HEARTS

    def test_card_from_string_unknown_suit(self):
        """Test creating card with unknown suit."""
        card = Card.from_string("K")
        assert card.rank == Rank.KING
        assert card.suit == Suit.UNKNOWN

    def test_card_value(self):
        """Test card values."""
        assert Card.from_string("A").value == 11
        assert Card.from_string("K").value == 10
        assert Card.from_string("Q").value == 10
        assert Card.from_string("J").value == 10
        assert Card.from_string("10").value == 10
        assert Card.from_string("5").value == 5
        assert Card.from_string("2").value == 2

    def test_is_ace(self):
        """Test ace detection."""
        assert Card.from_string("A").is_ace
        assert not Card.from_string("K").is_ace

    def test_card_string_representation(self):
        """Test card string output."""
        card = Card.from_string("A", "spades")
        assert "A" in str(card)
        assert "spades" in str(card)


class TestRank:
    """Tests for Rank enum."""

    def test_rank_from_symbol(self):
        """Test rank lookup from symbol."""
        assert Rank.from_symbol("A") == Rank.ACE
        assert Rank.from_symbol("K") == Rank.KING
        assert Rank.from_symbol("10") == Rank.TEN
        assert Rank.from_symbol("2") == Rank.TWO

    def test_rank_from_symbol_case_insensitive(self):
        """Test rank lookup is case insensitive."""
        assert Rank.from_symbol("a") == Rank.ACE
        assert Rank.from_symbol("k") == Rank.KING
        assert Rank.from_symbol("j") == Rank.JACK

    def test_rank_invalid_symbol(self):
        """Test invalid rank symbol raises error."""
        with pytest.raises(ValueError):
            Rank.from_symbol("X")


class TestHandValue:
    """Tests for hand value calculation."""

    def test_simple_hand(self):
        """Test simple hand value."""
        cards = [Card.from_string("5"), Card.from_string("7")]
        value, is_soft = calculate_hand_value(cards)
        assert value == 12
        assert not is_soft

    def test_face_cards(self):
        """Test face card values."""
        cards = [Card.from_string("K"), Card.from_string("Q")]
        value, _ = calculate_hand_value(cards)
        assert value == 20

    def test_soft_hand(self):
        """Test soft hand with ace."""
        cards = [Card.from_string("A"), Card.from_string("6")]
        value, is_soft = calculate_hand_value(cards)
        assert value == 17
        assert is_soft

    def test_hard_hand_with_ace(self):
        """Test ace counted as 1."""
        cards = [
            Card.from_string("A"),
            Card.from_string("6"),
            Card.from_string("8"),
        ]
        value, is_soft = calculate_hand_value(cards)
        assert value == 15
        assert not is_soft

    def test_multiple_aces(self):
        """Test multiple aces."""
        cards = [Card.from_string("A"), Card.from_string("A")]
        value, is_soft = calculate_hand_value(cards)
        assert value == 12
        assert is_soft

    def test_blackjack(self):
        """Test blackjack."""
        cards = [Card.from_string("A"), Card.from_string("K")]
        value, is_soft = calculate_hand_value(cards)
        assert value == 21
        assert is_soft

    def test_bust(self):
        """Test busted hand."""
        cards = [
            Card.from_string("K"),
            Card.from_string("Q"),
            Card.from_string("5"),
        ]
        value, _ = calculate_hand_value(cards)
        assert value == 25

    def test_three_aces(self):
        """Test three aces."""
        cards = [
            Card.from_string("A"),
            Card.from_string("A"),
            Card.from_string("A"),
        ]
        value, is_soft = calculate_hand_value(cards)
        assert value == 13
        assert is_soft


class TestMatch:
    """Tests for Match namedtuple."""

    def test_match_creation(self):
        """Test creating a match."""
        card = Card.from_string("A")
        match = Match(
            card=card,
            confidence=0.95,
            position=(100, 200),
            size=(50, 70),
        )
        assert match.card == card
        assert match.confidence == 0.95
        assert match.position == (100, 200)
        assert match.size == (50, 70)


class TestCardDetector:
    """Tests for CardDetector class."""

    def test_detector_initialization_no_templates(self):
        """Test detector initializes with missing template dir."""
        detector = CardDetector(
            template_dir="/nonexistent/path",
            confidence_threshold=0.85,
        )
        assert len(detector.templates) == 0

    def test_detector_confidence_threshold(self):
        """Test confidence threshold is set."""
        detector = CardDetector(
            template_dir="/nonexistent/path",
            confidence_threshold=0.90,
        )
        assert detector.confidence_threshold == 0.90

    def test_detect_cards_no_templates(self):
        """Test detection returns empty with no templates."""
        detector = CardDetector(template_dir="/nonexistent/path")
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        matches = detector.detect_cards(image)
        assert matches == []

    def test_preprocess_grayscale(self):
        """Test preprocessing converts to grayscale."""
        detector = CardDetector(template_dir="/nonexistent/path")
        color_image = np.zeros((100, 100, 3), dtype=np.uint8)
        processed = detector._preprocess(color_image)
        assert len(processed.shape) == 2  # Grayscale

    def test_preprocess_already_grayscale(self):
        """Test preprocessing handles grayscale input."""
        detector = CardDetector(template_dir="/nonexistent/path")
        gray_image = np.zeros((100, 100), dtype=np.uint8)
        processed = detector._preprocess(gray_image)
        assert len(processed.shape) == 2

    def test_non_max_suppression_empty(self):
        """Test NMS with empty list."""
        detector = CardDetector(template_dir="/nonexistent/path")
        result = detector._non_max_suppression([])
        assert result == []

    def test_non_max_suppression_single(self):
        """Test NMS with single match."""
        detector = CardDetector(template_dir="/nonexistent/path")
        match = Match(
            card=Card.from_string("A"),
            confidence=0.95,
            position=(100, 100),
            size=(50, 70),
        )
        result = detector._non_max_suppression([match])
        assert len(result) == 1
        assert result[0] == match

    def test_non_max_suppression_overlapping(self):
        """Test NMS removes overlapping matches."""
        detector = CardDetector(template_dir="/nonexistent/path")
        matches = [
            Match(
                card=Card.from_string("A"),
                confidence=0.95,
                position=(100, 100),
                size=(50, 70),
            ),
            Match(
                card=Card.from_string("K"),
                confidence=0.85,
                position=(105, 105),  # Overlapping
                size=(50, 70),
            ),
        ]
        result = detector._non_max_suppression(matches)
        assert len(result) == 1
        assert result[0].card.rank == Rank.ACE  # Higher confidence kept

    def test_non_max_suppression_non_overlapping(self):
        """Test NMS keeps non-overlapping matches."""
        detector = CardDetector(template_dir="/nonexistent/path")
        matches = [
            Match(
                card=Card.from_string("A"),
                confidence=0.95,
                position=(100, 100),
                size=(50, 70),
            ),
            Match(
                card=Card.from_string("K"),
                confidence=0.90,
                position=(200, 100),  # Not overlapping
                size=(50, 70),
            ),
        ]
        result = detector._non_max_suppression(matches)
        assert len(result) == 2
