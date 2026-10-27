from pathlib import Path

Path("escape").symlink_to("/tmp", target_is_directory=True)
print("DOCTOR_SYMLINK_CREATED", flush=True)
