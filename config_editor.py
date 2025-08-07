# config_editor.py
import importlib
import config as original_config
import hashlib
import json
import os
import textwrap

# --- New: List of keys that are not editable via the UI ---
uneditable_keys = [
    "BUY_SIGNAL",
    "FILE_PATH",
    "HOLD_SIGNAL",
    "OBSERVE_SIGNAL",
    "SELL_SIGNAL",
]

# Mutable copy of the original config, excluding uneditable keys
current = {
    k: getattr(original_config, k)
    for k in dir(original_config)
    if not k.startswith("_") and k.isupper() and k not in uneditable_keys
}

def get_dict() -> dict:
    """Return the live configuration."""
    return current

def update_dict(new_values: dict) -> None:
    """Merge new_values into the live configuration."""
    current.update({k: v for k, v in new_values.items() if k in current})

def reset_to_original() -> None:
    """Reload the original module and reset."""
    importlib.reload(original_config)
    current.update(
        {
            k: getattr(original_config, k)
            for k in dir(original_config)
            if not k.startswith("_") and k.isupper() and k not in uneditable_keys
        }
    )

def _hash_config() -> str:
    """
    Return an 8-char hash of the live config dict.
    Includes both editable and uneditable keys in the hash.
    """
    importlib.reload(original_config)
    full_config = current.copy()
    for key in uneditable_keys:
        if hasattr(original_config, key):
            full_config[key] = getattr(original_config, key)
            
    dump = json.dumps(full_config, sort_keys=True).encode()
    return hashlib.md5(dump).hexdigest()[:8]

def persist_config() -> None:
    """
    Overwrite config.py with a combination of the live (editable) values
    and the original (uneditable) values.
    """
    header = textwrap.dedent("""\
        # Auto-generated on Apply – do not hand-edit this block
        # The values below are written by the web Config tab.
        # Any manual changes above this line will be lost.

    """)
    lines = [header]

    importlib.reload(original_config)
    
    # Combine live editable values with static uneditable ones
    final_config = current.copy()
    for key in uneditable_keys:
        if hasattr(original_config, key):
            final_config[key] = getattr(original_config, key)

    # sort for deterministic order and write
    for k in sorted(final_config):
        v = final_config[k]
        lines.append(f"{k} = {repr(v)}\n")

    # write atomically
    tmp_path = "config.py.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.replace(tmp_path, "config.py")

    # reload so any new import sees the new values
    importlib.reload(original_config)