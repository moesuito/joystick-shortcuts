"""Set the current process priority class via Win32."""
from __future__ import annotations

import sys

NORMAL_PRIORITY_CLASS = 0x00000020
HIGH_PRIORITY_CLASS = 0x00000080
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000


def _kernel32():
    """Return kernel32 with HANDLE-aware restype/argtypes set up.

    On x64 Windows HANDLE is 64-bit, but ctypes defaults the return type to c_int (32-bit),
    which truncates the GetCurrentProcess pseudo-handle and makes SetPriorityClass fail.
    """
    import ctypes
    from ctypes import wintypes

    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.GetCurrentProcess.argtypes = []
    k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.SetPriorityClass.restype = wintypes.BOOL
    k.GetPriorityClass.argtypes = [wintypes.HANDLE]
    k.GetPriorityClass.restype = wintypes.DWORD
    return k


def set_priority_class(value: int) -> bool:
    if sys.platform != "win32":
        return False
    k = _kernel32()
    return bool(k.SetPriorityClass(k.GetCurrentProcess(), value))


def get_priority_class() -> int:
    if sys.platform != "win32":
        return 0
    k = _kernel32()
    return int(k.GetPriorityClass(k.GetCurrentProcess()))


def set_high_priority() -> bool:
    return set_priority_class(HIGH_PRIORITY_CLASS)


def set_normal_priority() -> bool:
    return set_priority_class(NORMAL_PRIORITY_CLASS)
