"""
Example Tool: Template for creating WAT framework tools

This demonstrates the expected pattern:
1. Load environment variables
2. Parse input arguments
3. Execute the task
4. Return or save results
5. Handle errors gracefully
"""

import os
import sys
from dotenv import load_dotenv


def main(input_param: str) -> dict:
    """
    Main execution function.

    Args:
        input_param: Description of what this parameter represents

    Returns:
        dict: Results with status and data

    Raises:
        ValueError: If input validation fails
        RuntimeError: If execution fails
    """
    # Load environment variables
    load_dotenv()

    # Validate inputs
    if not input_param:
        raise ValueError("input_param is required")

    # Example: Get API key from environment
    api_key = os.getenv("EXAMPLE_API_KEY")
    if not api_key:
        print("Warning: EXAMPLE_API_KEY not found in environment (this is expected for the example)")

    try:
        # Execute the actual work
        result = perform_task(input_param, api_key or "demo_key")

        return {
            "status": "success",
            "data": result
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def perform_task(input_param: str, api_key: str) -> str:
    """
    The actual work logic, separated for testability.

    Args:
        input_param: Input to process
        api_key: API key for external service

    Returns:
        str: Processed result
    """
    # This is where your actual logic goes
    # - Make API calls
    # - Transform data
    # - Write to cloud services
    # - etc.

    return f"Processed: {input_param}"


if __name__ == "__main__":
    # Command-line interface
    if len(sys.argv) < 2:
        print("Usage: python example_tool.py <input_param>")
        sys.exit(1)

    input_value = sys.argv[1]
    result = main(input_value)

    if result["status"] == "success":
        print(f"Success: {result['data']}")
        sys.exit(0)
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
