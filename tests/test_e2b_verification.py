"""
Simple test script for verification flow.
Launches environment, uploads solution, runs solution script, runs tests, downloads results.

Run: python tests/test_e2b_verification.py
"""

import asyncio
import json
from pathlib import Path

from humanlayer.environments.e2b import E2BEnvironment

BASE_DIR = Path(__file__).parent.parent
TASK_DIR = BASE_DIR / "examples" / "tasks" / "portfolio-optimization"
OUTPUT_DIR = BASE_DIR / "examples" / "jobs" / "test-verification"


async def main():
    env = E2BEnvironment(
        environment_dir=TASK_DIR / "environment",
        environment_name="test-verification",
        docker_image="alexgshaw/portfolio-optimization:20251031"
    )

    print("Starting e2b environment...")
    await env.start()

    try:
        import pdb; pdb.set_trace()
        work_dir = env.get_work_dir()
        print(f"Working directory: {work_dir}")

        # Upload solution
        solution_dir = TASK_DIR / "solution"
        if solution_dir.exists():
            print(f"\nUploading solution from {solution_dir}")
            await env.upload_dir(solution_dir, f"/{work_dir}/solution")
            print("Solution uploaded")

            # List what's in /solution
            result = await env.execute(f"ls -la /{work_dir}/solution")
            print(f"Solution directory contents:\n{result['output']}")

            # Run solution script in /app
            solve_script = solution_dir / "solve.sh"
            if solve_script.exists():
                print(f"\nRunning solution script in {work_dir}...")
                result = await env.execute(f"bash /{work_dir}/solution/solve.sh", cwd=work_dir)
                print(f"Solution output:\n{result['output']}")
                print(f"Solution return code: {result['returncode']}")

                # Show what's in /app after solution runs
                result = await env.execute("ls -la " + work_dir)
                print(f"\n{work_dir} directory after solution:\n{result['output']}")

        # Run verification
        print(f"\n{'='*60}")
        print("Running verification...")
        print(f"{'='*60}\n")

        # Upload tests
        tests_dir = TASK_DIR / "tests"
        if tests_dir.exists():
            print(f"Uploading tests from {tests_dir}")
            await env.upload_dir(tests_dir, "/tests")

        # Create logs directory
        await env.execute("mkdir -p /logs/verifier")

        # Run test script in /app
        test_script = tests_dir / "test.sh"
        if test_script.exists():
            print(f"Running test script in {work_dir}...")
            result = await env.execute("bash /tests/test.sh", cwd=work_dir)
            print(f"Test output:\n{result['output']}")
            print(f"Return code: {result['returncode']}")

            # Read the reward/result
            reward_result = await env.execute("cat /logs/verifier/reward.txt 2>/dev/null || echo 0")
            reward = reward_result.get('output', '0').strip()

            # Save result.json locally
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            result_data = {
                "success": int(reward) if reward.isdigit() else 0,
                "test_output": result.get('output', ''),
                "returncode": result.get('returncode', 1)
            }
            result_json_path = OUTPUT_DIR / "result.json"
            with open(result_json_path, 'w') as f:
                json.dump(result_data, f, indent=2)

            print(f"\n{'='*60}")
            print(f"Verification result: {result_data['success']}")
            print(f"Result saved to: {result_json_path}")
            print(f"{'='*60}\n")

        # Download environment
        download_path = OUTPUT_DIR / "environment_snapshot"
        print(f"Downloading environment to: {download_path}")
        await env.download_dir(target_dir=download_path)
        print("Download complete")

        # Show what we downloaded
        if download_path.exists():
            files = list(download_path.rglob("*"))
            print(f"\nDownloaded {len([f for f in files if f.is_file()])} files")
            print("Sample files:")
            for f in sorted(files)[:10]:
                if f.is_file():
                    print(f"  - {f.relative_to(download_path)}")

    finally:
        print("\nStopping environment...")
        await env.stop()


if __name__ == "__main__":
    asyncio.run(main())
