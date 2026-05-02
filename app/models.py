"""Data models for bindings, profiles, and app config."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Literal


XINPUT_BUTTONS = [
    "A", "B", "X", "Y",
    "LB", "RB",
    "LT", "RT",
    "BACK", "START",
    "LS", "RS",
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
]

ActionType = Literal["key", "key_combo", "media", "launch"]
TriggerMode = Literal["press", "release", "hold"]


@dataclass
class Action:
    type: ActionType
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type, "payload": self.payload}

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        return cls(type=data["type"], payload=data.get("payload", {}))


@dataclass
class Binding:
    name: str
    button: str
    action: Action
    trigger: TriggerMode = "press"
    hold_ms: int = 500
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "button": self.button,
            "trigger": self.trigger,
            "hold_ms": self.hold_ms,
            "action": self.action.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Binding":
        return cls(
            id=data.get("id") or uuid.uuid4().hex,
            name=data["name"],
            button=data["button"],
            trigger=data.get("trigger", "press"),
            hold_ms=int(data.get("hold_ms", 500)),
            action=Action.from_dict(data["action"]),
        )


@dataclass
class Profile:
    name: str
    bindings: list[Binding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "bindings": [b.to_dict() for b in self.bindings]}

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            name=data["name"],
            bindings=[Binding.from_dict(b) for b in data.get("bindings", [])],
        )


@dataclass
class AppConfig:
    active_profile: str = "Default"
    autostart: bool = False
    high_priority: bool = True
    poll_hz: int = 120
    minimize_to_tray_on_start: bool = True
    trigger_threshold: float = 0.5
    paused: bool = False
    profiles: dict[str, Profile] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "active_profile": self.active_profile,
            "autostart": self.autostart,
            "high_priority": self.high_priority,
            "poll_hz": self.poll_hz,
            "minimize_to_tray_on_start": self.minimize_to_tray_on_start,
            "trigger_threshold": self.trigger_threshold,
            "paused": self.paused,
            "profiles": {name: p.to_dict() for name, p in self.profiles.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        cfg = cls(
            active_profile=data.get("active_profile", "Default"),
            autostart=bool(data.get("autostart", False)),
            high_priority=bool(data.get("high_priority", True)),
            poll_hz=int(data.get("poll_hz", 120)),
            minimize_to_tray_on_start=bool(data.get("minimize_to_tray_on_start", True)),
            trigger_threshold=float(data.get("trigger_threshold", 0.5)),
            paused=bool(data.get("paused", False)),
            profiles={
                name: Profile.from_dict(p)
                for name, p in (data.get("profiles") or {}).items()
            },
        )
        if not cfg.profiles:
            cfg.profiles["Default"] = Profile(name="Default")
            cfg.active_profile = "Default"
        return cfg

    def active(self) -> Profile:
        if self.active_profile not in self.profiles:
            # Fallback: pick any or create a default.
            if self.profiles:
                self.active_profile = next(iter(self.profiles))
            else:
                self.profiles["Default"] = Profile(name="Default")
                self.active_profile = "Default"
        return self.profiles[self.active_profile]
