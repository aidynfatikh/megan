import asyncio
import os
import signal


class ProcessError(RuntimeError):
    pass


async def run_process(*args: str, timeout: float, env=None) -> tuple[bytes, bytes]:
    """Await termination before returning, including timeout and cancellation paths."""
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=os.name != "nt",
            env=env,
        )
    except FileNotFoundError as exc:
        raise ProcessError(f"Executable not found: {args[0]}. Run preflight/setup.") from exc
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            try:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
        await process.communicate()
        raise
    if process.returncode:
        raise ProcessError(
            stderr.decode(errors="replace")[-2000:] or f"{args[0]} exited with {process.returncode}"
        )
    return stdout, stderr
