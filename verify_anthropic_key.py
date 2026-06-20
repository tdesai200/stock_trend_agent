import argparse
import os
import sys
from pathlib import Path


def load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv is not installed. Install it with `pip install python-dotenv`.")
        sys.exit(1)

    env_path = Path(__file__).parent / ".env"
    print(f".env file exists: {env_path.exists()}")
    if env_path.exists():
        load_dotenv(env_path)


def get_key(key_arg: str | None) -> str | None:
    if key_arg:
        return key_arg.strip()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key is None:
        return None
    api_key = api_key.strip()
    if len(api_key) >= 2 and api_key[0] == api_key[-1] and api_key[0] in {'"', "'"}:
        api_key = api_key[1:-1].strip()
    return api_key


def print_env_state():
    raw = os.environ.get("ANTHROPIC_API_KEY")
    print(f"Raw ANTHROPIC_API_KEY from environment: {repr(raw)}")
    if raw is not None:
        print(f"Length: {len(raw)}")
        print(f"Starts with: {raw[:4]!r}")
        print(f"Ends with: {raw[-4:]!r}")


def main():
    parser = argparse.ArgumentParser(description="Verify Anthropic API key loading and test connectivity.")
    parser.add_argument("--key", help="Optional explicit Anthropic API key to test.")
    parser.add_argument("--limit", type=int, default=1, help="Number of models to request when listing models.")
    args = parser.parse_args()

    load_env()
    api_key = get_key(args.key)
    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY was found in environment or supplied with --key.")
        sys.exit(1)

    print_env_state()
    print(f"Using ANTHROPIC_API_KEY length: {len(api_key)}")
    print(f"Using Anthropic package from: {os.__file__}")

    try:
        import anthropic
    except ImportError:
        print("ERROR: The Anthropic Python SDK is not installed. Install it with `pip install anthropic`.")
        sys.exit(1)

    print(f"Anthropic SDK version: {getattr(anthropic, '__version__', 'unknown')}")

    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as exc:
        print(f"ERROR: Failed to create Anthropic client: {exc}")
        sys.exit(1)

    try:
        print("Calling client.models.list()...")
        response = client.models.list(limit=args.limit)
        print("SUCCESS: Received model list response.")
        print(response)
    except Exception as exc:
        print("ERROR: Anthropic API model list failed.")
        print(type(exc).__name__)
        print(exc)
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
