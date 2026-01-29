"""
Simple test script for e2b environment.
Launches environment, creates a file, downloads the directory.

Run: python examples/test_e2b.py
"""

import asyncio
from pathlib import Path

from humanlayer.environments.e2b import E2BEnvironment

BASE_DIR = Path(__file__).parent.parent
TASK_NAME = "portfolio-optimization"
TASK_DIR = BASE_DIR / "examples" / "tasks" / TASK_NAME


async def main():
    env = E2BEnvironment(
        environment_dir=TASK_DIR / "environment",
        environment_name=TASK_NAME,
        docker_image="alexgshaw/portfolio-optimization:20251031"
    )

    print("Starting e2b environment...")
    await env.start()

    try:
        # Check working directory
        result = await env.execute("pwd")
        print(f"Working dir: {result['output'].strip()}")

        # List files
        result = await env.execute("ls -la")
        print(f"Files:\n{result['output']}")

        # Create a test file
        result = await env.execute("echo 'Hello from e2b!' > test_file.txt")
        print(f"Created test_file.txt")

        # Verify it exists
        result = await env.execute("cat test_file.txt")
        print(f"Content: {result['output'].strip()}")

        # Download the directory
        download_path = BASE_DIR / "examples" / "jobs" / "test-e2b-download"
        print(f"\nDownloading to: {download_path}")
        await env.download_dir(target_dir=download_path)

        # Verify download
        downloaded_file = download_path / "test_file.txt"
        if downloaded_file.exists():
            print(f"Downloaded file content: {downloaded_file.read_text().strip()}")
        else:
            print(f"Warning: test_file.txt not found in download")

    finally:
        print("\nStopping environment...")
        await env.stop()


if __name__ == "__main__":
    asyncio.run(main())
