# -*- coding: utf-8 -*-
"""Sorting-control abstraction.

The physical mechanism is NOT connected in this project.  This module defines
the interface the UI uses and a simulated implementation; a real serial/ESP32
controller must implement the same ``command()`` contract.

Bin assignment is a design choice for the demo: four suit bins + a review bin.
It is not claimed to be the team's final mechanical layout.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

BIN_BY_SUIT = {"S": "BIN_SPADE", "H": "BIN_HEART", "D": "BIN_DIAMOND", "C": "BIN_CLUB"}
BIN_LABEL = {
    "BIN_SPADE": "黑桃槽",
    "BIN_HEART": "红心槽",
    "BIN_DIAMOND": "方块槽",
    "BIN_CLUB": "梅花槽",
    "REVIEW": "复核槽",
}


@dataclass
class SortCommand:
    label: str
    bin: str
    bin_label: str
    simulated: bool
    note: str = ""


class SortingController:
    """Simulated controller used by the demo UI."""

    def __init__(self, simulated: bool = True):
        self.simulated = simulated
        self.commands = 0

    def command(self, label: str) -> SortCommand:
        self.commands += 1
        raw = str(label).upper()
        if raw == "JOKER":
            return SortCommand(raw, "REVIEW", BIN_LABEL["REVIEW"], self.simulated,
                               "Joker / manual review")
        suit = raw[-1] if raw else ""
        if suit in BIN_BY_SUIT:
            b = BIN_BY_SUIT[suit]
            return SortCommand(raw, b, BIN_LABEL[b], self.simulated,
                               "suit-based simulated bin")
        return SortCommand(raw, "REVIEW", BIN_LABEL["REVIEW"], self.simulated,
                           "unknown label -> manual review")

    def execute(self, command: SortCommand) -> dict:
        if not self.simulated:
            raise NotImplementedError("real hardware protocol is not implemented")
        return {"executed": True, "simulated": True, "bin": command.bin,
                "note": "界面演示：未驱动真实电机"}


class SerialSortingController(SortingController):
    """Placeholder for the real ESP32/serial controller.

    A real implementation should open the serial port, send the bin command and
    wait for an ACK/timeout.  It is intentionally not faked here.
    """

    def __init__(self, port: str, baud: int = 115200):
        super().__init__(simulated=False)
        self.port = port
        self.baud = baud

    def execute(self, command: SortCommand) -> dict:
        raise NotImplementedError(
            "机械/ESP32 控制未接入：请在此实现串口协议并做硬件联调")
