"""Card detection module using template matching.

This module provides computer vision functionality to detect playing cards
in screen captures using OpenCV template matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class Suit(Enum):
    """Card suits."""
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"
    SPADES = "spades"
    UNKNOWN = "unknown"


class Rank(Enum):
    """Card ranks with their blackjack values."""
    TWO = ("2", 2)
    THREE = ("3", 3)
    FOUR = ("4", 4)
    FIVE = ("5", 5)
    SIX = ("6", 6)
    SEVEN = ("7", 7)
    EIGHT = ("8", 8)
    NINE = ("9", 9)
    TEN = ("10", 10)
    JACK = ("J", 10)
    QUEEN = ("Q", 10)
    KING = ("K", 10)
    ACE = ("A", 11)  # Value can be 1 or 11

    def __init__(self, symbol: str, value: int) -> None:
        self.symbol = symbol
        self.base_value = value

    @classmethod
    def from_symbol(cls, symbol: str) -> Rank:
        """Get rank from symbol string."""
        symbol_upper = symbol.upper()
        for rank in cls:
            if rank.symbol == symbol_upper:
                return rank
        raise ValueError(f"Unknown rank symbol: {symbol}")


@dataclass
class Card:
    """Represents a playing card.

    Attributes:
        rank: The card rank (2-10, J, Q, K, A).
        suit: The card suit.
    """
    rank: Rank
    suit: Suit = Suit.UNKNOWN

    @classmethod
    def from_string(cls, rank_str: str, suit_str: str = "unknown") -> Card:
        """Create card from string representations.

        Args:
            rank_str: Rank as string (e.g., "A", "10", "K").
            suit_str: Suit as string (e.g., "hearts", "spades").

        Returns:
            Card instance.
        """
        rank = Rank.from_symbol(rank_str)
        try:
            suit = Suit(suit_str.lower())
        except ValueError:
            suit = Suit.UNKNOWN
        return cls(rank=rank, suit=suit)

    @property
    def value(self) -> int:
        """Get the base blackjack value of this card."""
        return self.rank.base_value

    @property
    def is_ace(self) -> bool:
        """Check if this card is an ace."""
        return self.rank == Rank.ACE

    def __str__(self) -> str:
        """String representation."""
        if self.suit != Suit.UNKNOWN:
            return f"{self.rank.symbol} of {self.suit.value}"
        return self.rank.symbol

    def __repr__(self) -> str:
        return f"Card({self.rank.symbol!r}, {self.suit.value!r})"


class Match(NamedTuple):
    """Represents a template match result.

    Attributes:
        card: The detected card.
        confidence: Match confidence score (0.0 to 1.0).
        position: (x, y) position of the top-left corner.
        size: (width, height) of the match.
    """
    card: Card
    confidence: float
    position: tuple[int, int]
    size: tuple[int, int]


class CardDetectionError(Exception):
    """Raised when card detection fails."""
    pass


class CardDetector:
    """Detects playing cards using template matching.

    This detector uses OpenCV's template matching to find cards in
    screen captures. It requires pre-captured templates for each card rank.

    Example:
        >>> detector = CardDetector("src/vision/templates")
        >>> cards = detector.detect_cards(image)
        >>> for card, confidence, pos in cards:
        ...     print(f"Found {card} at {pos} with {confidence:.2f} confidence")
    """

    # Rank symbols for template file naming
    RANK_SYMBOLS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

    def __init__(
        self,
        template_dir: str | Path,
        confidence_threshold: float = 0.85,
        scale_range: tuple[float, float] = (0.8, 1.2),
        scale_steps: int = 5,
    ) -> None:
        """Initialize the card detector.

        Args:
            template_dir: Directory containing template images.
            confidence_threshold: Minimum confidence for valid match.
            scale_range: (min, max) scale factors for multi-scale matching.
            scale_steps: Number of scale steps to try.
        """
        self.template_dir = Path(template_dir)
        self.confidence_threshold = confidence_threshold
        self.scale_range = scale_range
        self.scale_steps = scale_steps
        self.templates: dict[str, np.ndarray] = {}

        self._load_templates()
        logger.info(
            "card_detector_initialized",
            template_dir=str(template_dir),
            templates_loaded=len(self.templates),
            confidence_threshold=confidence_threshold,
        )

    def _load_templates(self) -> None:
        """Load all card templates from directory."""
        if not self.template_dir.exists():
            logger.warning("template_dir_not_found", path=str(self.template_dir))
            return

        # Try different naming conventions
        patterns = [
            "{rank}.png",          # Simple: A.png, 10.png
            "{rank}_*.png",        # With suit: A_hearts.png
            "card_{rank}.png",     # Prefixed: card_A.png
        ]

        for rank in self.RANK_SYMBOLS:
            for pattern in patterns:
                template_path = self.template_dir / pattern.format(rank=rank)
                if template_path.exists():
                    template = cv2.imread(str(template_path))
                    if template is not None:
                        self.templates[rank] = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                        logger.debug("template_loaded", rank=rank, path=str(template_path))
                        break

                # Also try glob for patterns with wildcards
                for match in self.template_dir.glob(pattern.format(rank=rank)):
                    template = cv2.imread(str(match))
                    if template is not None:
                        self.templates[rank] = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                        logger.debug("template_loaded", rank=rank, path=str(match))
                        break

    def detect_cards(
        self,
        image: np.ndarray,
        max_cards: int = 10,
    ) -> list[Match]:
        """Detect all cards in an image.

        Args:
            image: Input image in BGR format.
            max_cards: Maximum number of cards to detect.

        Returns:
            List of Match objects for detected cards, sorted by x-position.
        """
        if len(self.templates) == 0:
            logger.warning("no_templates_loaded")
            return []

        # Preprocess image
        gray = self._preprocess(image)

        # Find all matches
        all_matches: list[Match] = []

        for rank, template in self.templates.items():
            matches = self._match_template(gray, template, rank)
            all_matches.extend(matches)

        # Apply non-maximum suppression
        filtered_matches = self._non_max_suppression(all_matches)

        # Sort by x-position (left to right)
        filtered_matches.sort(key=lambda m: m.position[0])

        # Limit to max_cards
        if len(filtered_matches) > max_cards:
            filtered_matches = filtered_matches[:max_cards]

        logger.debug(
            "cards_detected",
            count=len(filtered_matches),
            cards=[str(m.card) for m in filtered_matches],
        )

        return filtered_matches

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for template matching.

        Args:
            image: Input BGR image.

        Returns:
            Preprocessed grayscale image.
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Apply adaptive thresholding for better contrast
        # gray = cv2.adaptiveThreshold(
        #     gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        #     cv2.THRESH_BINARY, 11, 2
        # )

        # Normalize
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

        return gray

    def _match_template(
        self,
        image: np.ndarray,
        template: np.ndarray,
        rank: str,
    ) -> list[Match]:
        """Find all matches of a template in the image.

        Uses multi-scale template matching to handle size variations.

        Args:
            image: Preprocessed grayscale image.
            template: Template image to find.
            rank: The rank symbol this template represents.

        Returns:
            List of Match objects above confidence threshold.
        """
        matches: list[Match] = []
        h, w = template.shape[:2]

        # Generate scale factors
        scales = np.linspace(
            self.scale_range[0],
            self.scale_range[1],
            self.scale_steps,
        )

        for scale in scales:
            # Resize template
            new_w = int(w * scale)
            new_h = int(h * scale)

            if new_w < 10 or new_h < 10:
                continue

            if new_w > image.shape[1] or new_h > image.shape[0]:
                continue

            scaled_template = cv2.resize(
                template,
                (new_w, new_h),
                interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
            )

            # Perform template matching
            result = cv2.matchTemplate(
                image,
                scaled_template,
                cv2.TM_CCOEFF_NORMED,
            )

            # Find all locations above threshold
            locations = np.where(result >= self.confidence_threshold)

            for pt in zip(*locations[::-1]):  # Switch x and y
                confidence = result[pt[1], pt[0]]

                match = Match(
                    card=Card.from_string(rank),
                    confidence=float(confidence),
                    position=(int(pt[0]), int(pt[1])),
                    size=(new_w, new_h),
                )
                matches.append(match)

        return matches

    def _non_max_suppression(
        self,
        matches: list[Match],
        overlap_threshold: float = 0.5,
    ) -> list[Match]:
        """Remove overlapping detections, keeping highest confidence.

        Args:
            matches: List of all matches.
            overlap_threshold: IoU threshold for considering overlap.

        Returns:
            Filtered list of matches.
        """
        if len(matches) == 0:
            return []

        # Sort by confidence (descending)
        matches = sorted(matches, key=lambda m: m.confidence, reverse=True)

        # Convert to numpy arrays for efficient computation
        boxes = np.array([
            [m.position[0], m.position[1],
             m.position[0] + m.size[0], m.position[1] + m.size[1]]
            for m in matches
        ])

        # Compute areas
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])

        keep = []
        indices = list(range(len(matches)))

        while indices:
            # Keep the highest confidence match
            current = indices[0]
            keep.append(current)
            indices = indices[1:]

            if not indices:
                break

            # Compute IoU with remaining boxes
            remaining_boxes = boxes[indices]
            current_box = boxes[current]

            # Intersection
            xx1 = np.maximum(current_box[0], remaining_boxes[:, 0])
            yy1 = np.maximum(current_box[1], remaining_boxes[:, 1])
            xx2 = np.minimum(current_box[2], remaining_boxes[:, 2])
            yy2 = np.minimum(current_box[3], remaining_boxes[:, 3])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)

            intersection = w * h
            union = areas[current] + areas[indices] - intersection
            iou = intersection / union

            # Keep only non-overlapping boxes
            indices = [idx for i, idx in enumerate(indices) if iou[i] < overlap_threshold]

        return [matches[i] for i in keep]

    def detect_dealer_upcard(self, image: np.ndarray) -> Card | None:
        """Detect the dealer's visible upcard.

        Args:
            image: Image of the dealer card area.

        Returns:
            The detected Card, or None if not found.
        """
        matches = self.detect_cards(image, max_cards=2)

        # Return the first (leftmost) card, which should be the upcard
        if matches:
            return matches[0].card

        return None

    def detect_player_hand(self, image: np.ndarray) -> list[Card]:
        """Detect all cards in the player's hand.

        Args:
            image: Image of the player card area.

        Returns:
            List of detected Cards, ordered left to right.
        """
        matches = self.detect_cards(image)
        return [m.card for m in matches]


class TemplateCaptureTool:
    """Tool for capturing card templates from screen.

    This helps users create template images by capturing individual
    cards from their game.
    """

    def __init__(self, output_dir: str | Path) -> None:
        """Initialize template capture tool.

        Args:
            output_dir: Directory to save captured templates.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture_template(
        self,
        image: np.ndarray,
        rank: str,
        suit: str | None = None,
    ) -> Path:
        """Save an image as a card template.

        Args:
            image: The card image to save.
            rank: The card rank (e.g., "A", "10").
            suit: Optional suit name.

        Returns:
            Path to the saved template.
        """
        if suit:
            filename = f"{rank}_{suit}.png"
        else:
            filename = f"{rank}.png"

        filepath = self.output_dir / filename
        cv2.imwrite(str(filepath), image)

        logger.info("template_captured", rank=rank, suit=suit, path=str(filepath))
        return filepath

    def capture_from_region(
        self,
        screen_image: np.ndarray,
        x: int,
        y: int,
        width: int,
        height: int,
        rank: str,
        suit: str | None = None,
    ) -> Path:
        """Capture a template from a region of a screen image.

        Args:
            screen_image: Full screen capture.
            x, y: Top-left corner of the card.
            width, height: Size of the card region.
            rank: The card rank.
            suit: Optional suit.

        Returns:
            Path to the saved template.
        """
        card_image = screen_image[y:y+height, x:x+width]
        return self.capture_template(card_image, rank, suit)


def calculate_hand_value(cards: list[Card]) -> tuple[int, bool]:
    """Calculate the blackjack value of a hand.

    Args:
        cards: List of cards in the hand.

    Returns:
        Tuple of (value, is_soft) where is_soft indicates if an ace
        is being counted as 11.
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
    soft = aces > 0
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    # Hand is soft if there's still an ace counted as 11
    is_soft = aces > 0 and total <= 21

    return total, is_soft
