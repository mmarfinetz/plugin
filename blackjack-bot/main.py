#!/usr/bin/env python3
"""Blackjack Bot - Main Entry Point.

This script provides the command-line interface for the blackjack bot,
including calibration, testing, and running modes.

Usage:
    # Run calibration to set up screen regions
    python main.py --calibrate

    # Run bot in dry-run mode (no actual clicks)
    python main.py --dry-run

    # Run bot in live mode
    python main.py

    # Test card detection
    python main.py --test-detection

    # Test strategy
    python main.py --test-strategy

macOS Permissions:
    The bot requires Screen Recording permission:
    System Preferences -> Privacy & Security -> Screen Recording
    Add Terminal/IDE to allowed apps and restart terminal.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import structlog


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging.

    Args:
        verbose: If True, enable debug logging.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    import logging
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if verbose else logging.INFO,
    )


def run_calibration(config_path: str) -> int:
    """Run the calibration tool.

    Args:
        config_path: Path to save the configuration.

    Returns:
        Exit code (0 for success).
    """
    from src.capture.calibration import run_calibration, validate_config

    print("\n" + "=" * 60)
    print("BLACKJACK BOT - CALIBRATION MODE")
    print("=" * 60)
    print(f"\nConfiguration will be saved to: {config_path}")

    try:
        config = run_calibration(config_path)

        # Validate configuration
        is_valid, issues = validate_config(config)

        if is_valid:
            print("\n" + "=" * 60)
            print("CALIBRATION COMPLETE")
            print("=" * 60)
            print(f"\nRegions calibrated: {list(config.regions.keys())}")
            print(f"Configuration saved to: {config_path}")
            print("\nYou can now run the bot with:")
            print(f"  python main.py --dry-run --config {config_path}")
            return 0
        else:
            print("\n" + "=" * 60)
            print("CALIBRATION INCOMPLETE")
            print("=" * 60)
            print("\nIssues found:")
            for issue in issues:
                print(f"  - {issue}")
            return 1

    except KeyboardInterrupt:
        print("\nCalibration cancelled.")
        return 1
    except Exception as e:
        print(f"\nCalibration error: {e}")
        return 1


def run_bot(config_path: str, dry_run: bool, template_dir: str) -> int:
    """Run the blackjack bot.

    Args:
        config_path: Path to configuration file.
        dry_run: If True, simulate actions.
        template_dir: Directory containing card templates.

    Returns:
        Exit code (0 for success).
    """
    from src.bot import BlackjackBot

    # Check if config exists
    if not Path(config_path).exists():
        print(f"\nError: Configuration file not found: {config_path}")
        print("Please run calibration first:")
        print(f"  python main.py --calibrate --config {config_path}")
        return 1

    print("\n" + "=" * 60)
    print("BLACKJACK BOT")
    print("=" * 60)
    print(f"\nMode: {'DRY RUN (no clicks)' if dry_run else 'LIVE'}")
    print(f"Config: {config_path}")
    print("\nSafety features:")
    print("  - Move mouse to any corner to STOP")
    print("  - Press Ctrl+C to stop")
    print("\n" + "=" * 60)

    if not dry_run:
        print("\nWARNING: Live mode - bot will click buttons!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return 0

    try:
        bot = BlackjackBot(
            config_path=config_path,
            dry_run=dry_run,
            template_dir=template_dir,
        )
        bot.run()

        # Print final stats
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        stats = bot.stats.get_summary()
        print(f"Hands played: {stats['hands_played']}")
        print(f"Actions taken: {stats['actions_taken']}")
        print(f"Errors: {stats['errors']}")
        print(f"Duration: {stats['elapsed_seconds']:.1f} seconds")
        if stats['action_breakdown']:
            print("\nAction breakdown:")
            for action, count in stats['action_breakdown'].items():
                print(f"  {action}: {count}")

        return 0

    except KeyboardInterrupt:
        print("\nBot stopped by user.")
        return 0
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("Please run calibration first.")
        return 1
    except Exception as e:
        print(f"\nBot error: {e}")
        return 1


def test_detection(config_path: str, template_dir: str) -> int:
    """Test card detection.

    Args:
        config_path: Path to configuration file.
        template_dir: Directory containing card templates.

    Returns:
        Exit code.
    """
    from src.bot import BlackjackBot

    if not Path(config_path).exists():
        print(f"\nError: Configuration file not found: {config_path}")
        return 1

    print("\n" + "=" * 60)
    print("CARD DETECTION TEST")
    print("=" * 60)
    print("\nPress Ctrl+C to stop testing.\n")

    bot = BlackjackBot(
        config_path=config_path,
        dry_run=True,
        template_dir=template_dir,
    )

    try:
        while True:
            result = bot.test_detection()
            print(f"\rPlayer: {result['player_cards']} | "
                  f"Dealer: {result['dealer_upcard']} | "
                  f"Value: {result['hand_value']} | "
                  f"Valid: {result['is_valid']}     ", end="")
            import time
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\nTest complete.")
        return 0


def test_strategy() -> int:
    """Interactive strategy testing.

    Returns:
        Exit code.
    """
    from src.strategy.basic import Action, get_optimal_action
    from src.vision.detector import Card

    print("\n" + "=" * 60)
    print("BASIC STRATEGY TESTER")
    print("=" * 60)
    print("\nEnter cards to test strategy decisions.")
    print("Card format: 2-10, J, Q, K, A")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            # Get player cards
            player_input = input("Player cards (comma-separated, e.g., 'A,7'): ").strip()
            if player_input.lower() == 'quit':
                break

            player_symbols = [s.strip().upper() for s in player_input.split(',')]
            player_cards = [Card.from_string(s) for s in player_symbols]

            # Get dealer card
            dealer_input = input("Dealer upcard (e.g., '10'): ").strip().upper()
            if dealer_input.lower() == 'quit':
                break

            dealer_card = Card.from_string(dealer_input)

            # Calculate action
            from src.strategy.basic import is_pair, calculate_hand_value

            can_split = is_pair(player_cards)
            value, is_soft = calculate_hand_value(player_cards)

            action = get_optimal_action(
                player_cards=player_cards,
                dealer_upcard=dealer_card,
                can_double=True,
                can_split=can_split,
                can_surrender=True,
            )

            # Display result
            print(f"\n  Player: {[str(c) for c in player_cards]}")
            print(f"  Value: {value} ({'soft' if is_soft else 'hard'})")
            print(f"  Dealer: {dealer_card}")
            print(f"  >>> Optimal action: {action} <<<\n")

        except ValueError as e:
            print(f"  Error: {e}\n")
        except KeyboardInterrupt:
            break

    print("\nStrategy test complete.")
    return 0


def capture_templates(output_dir: str) -> int:
    """Interactive template capture tool.

    Args:
        output_dir: Directory to save templates.

    Returns:
        Exit code.
    """
    from src.capture.screen import ScreenCapture
    from src.vision.detector import TemplateCaptureTool

    print("\n" + "=" * 60)
    print("TEMPLATE CAPTURE TOOL")
    print("=" * 60)
    print(f"\nTemplates will be saved to: {output_dir}")
    print("\nInstructions:")
    print("1. Position a card on screen")
    print("2. Enter the card rank when prompted")
    print("3. Select the card region")
    print("4. Repeat for all cards")
    print("\nType 'quit' to exit.\n")

    import cv2

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    capture = ScreenCapture()
    tool = TemplateCaptureTool(output_path)

    try:
        while True:
            rank = input("Enter card rank (2-10, J, Q, K, A) or 'quit': ").strip().upper()
            if rank.lower() == 'quit':
                break

            if rank not in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']:
                print("  Invalid rank. Try again.")
                continue

            # Capture screen
            screenshot = capture.capture_full_screen()

            # Let user select region
            print("  Select the card region in the window...")
            roi = cv2.selectROI("Select Card", screenshot, fromCenter=False)
            cv2.destroyWindow("Select Card")

            if roi[2] > 0 and roi[3] > 0:
                filepath = tool.capture_from_region(
                    screenshot,
                    x=int(roi[0]),
                    y=int(roi[1]),
                    width=int(roi[2]),
                    height=int(roi[3]),
                    rank=rank,
                )
                print(f"  Saved: {filepath}\n")
            else:
                print("  Selection cancelled.\n")

    except KeyboardInterrupt:
        pass
    finally:
        capture.close()
        cv2.destroyAllWindows()

    print("\nTemplate capture complete.")
    return 0


def main() -> int:
    """Main entry point.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        description="Blackjack Bot - Automated blackjack player using computer vision",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --calibrate              Run calibration wizard
  python main.py --dry-run                Run bot without clicking
  python main.py                          Run bot in live mode
  python main.py --test-detection         Test card detection
  python main.py --test-strategy          Interactive strategy tester
  python main.py --capture-templates      Capture card templates

Safety:
  Move mouse to any corner to trigger failsafe and stop the bot.
  Press Ctrl+C at any time to stop.

macOS:
  Requires Screen Recording permission in System Preferences.
        """,
    )

    # Mode arguments (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--calibrate",
        action="store_true",
        help="Run calibration wizard to set up screen regions",
    )
    mode_group.add_argument(
        "--test-detection",
        action="store_true",
        help="Test card detection without taking actions",
    )
    mode_group.add_argument(
        "--test-strategy",
        action="store_true",
        help="Interactive basic strategy tester",
    )
    mode_group.add_argument(
        "--capture-templates",
        action="store_true",
        help="Capture card templates for detection",
    )

    # Options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate actions without actually clicking",
    )
    parser.add_argument(
        "--config",
        default="config/regions.json",
        help="Path to configuration file (default: config/regions.json)",
    )
    parser.add_argument(
        "--template-dir",
        default="src/vision/templates",
        help="Directory containing card templates (default: src/vision/templates)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Change to script directory for relative paths
    script_dir = Path(__file__).parent
    import os
    os.chdir(script_dir)

    # Run appropriate mode
    if args.calibrate:
        return run_calibration(args.config)
    elif args.test_detection:
        return test_detection(args.config, args.template_dir)
    elif args.test_strategy:
        return test_strategy()
    elif args.capture_templates:
        return capture_templates(args.template_dir)
    else:
        return run_bot(args.config, args.dry_run, args.template_dir)


if __name__ == "__main__":
    sys.exit(main())
