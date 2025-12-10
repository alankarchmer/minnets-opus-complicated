"""
Judge Logger: Training data collection for context routing.

Logs every judge decision and user feedback for future model training.
Uses async file I/O to avoid blocking the main thread.

Log format (JSONL):
{"type": "decision", "request_id": "abc", "timestamp": 1234567890.0, "app_name": "Safari", ...}
{"type": "feedback", "request_id": "abc", "insight_id": "xyz", "signal": "click", ...}
"""

import json
import time
import os
from pathlib import Path
from typing import Optional

import aiofiles

from models import StrategyWeights
from config import get_settings


class JudgeLogger:
    """
    Async logger for training data collection.
    
    Logs two types of events:
    1. Decisions: Context -> StrategyWeights mapping (input -> label)
    2. Feedback: User response to insights (for reward signal)
    
    Data is stored in JSONL format for easy streaming/loading.
    """
    
    def __init__(self, filepath: str = None):
        settings = get_settings()
        self.filepath = filepath or settings.judge_log_path
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Create the training_data directory if it doesn't exist."""
        directory = Path(self.filepath).parent
        directory.mkdir(parents=True, exist_ok=True)
    
    async def log_decision(
        self,
        request_id: str,
        app_name: str,
        window_title: str,
        weights: StrategyWeights,
        insight_ids: list[str],
        context_len: int = 0,
        retrieval_path: str = None
    ):
        """
        Log a routing decision for training.
        
        Args:
            request_id: Unique ID for this request (for joining with feedback)
            app_name: Active application name
            window_title: Active window title
            weights: The StrategyWeights determined by the judge
            insight_ids: IDs of insights returned to user
            context_len: Length of context (don't log full text for privacy)
            retrieval_path: Which retrieval path was actually used
        """
        entry = {
            "type": "decision",
            "timestamp": time.time(),
            "request_id": request_id,
            "app_name": app_name,
            "window_title": window_title[:100] if window_title else "",
            "weights": weights.model_dump(),
            "insight_ids": insight_ids,
            "context_len": context_len,
            "retrieval_path": retrieval_path
        }
        
        await self._write_entry(entry)
    
    async def log_feedback(
        self,
        request_id: str,
        insight_id: str,
        feedback_type: str,
        dwell_time_ms: Optional[int] = None,
        position_in_list: Optional[int] = None,
        metadata: Optional[dict] = None
    ):
        """
        Log user feedback on an insight.
        
        Args:
            request_id: ID of the original /analyze request
            insight_id: ID of the suggestion being rated
            feedback_type: Type of feedback (click, dwell, dismiss, thumbs_up, etc.)
            dwell_time_ms: How long user engaged with the insight
            position_in_list: Where the insight appeared (0, 1, 2)
            metadata: Additional context
        """
        entry = {
            "type": "feedback",
            "timestamp": time.time(),
            "request_id": request_id,
            "insight_id": insight_id,
            "signal": feedback_type,
            "dwell_time_ms": dwell_time_ms,
            "position": position_in_list,
            "metadata": metadata or {}
        }
        
        await self._write_entry(entry)
    
    async def _write_entry(self, entry: dict):
        """Write a single entry to the log file."""
        try:
            async with aiofiles.open(self.filepath, mode='a') as f:
                await f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Don't fail the main request if logging fails
            print(f"   ⚠️ JudgeLogger write error: {e}")
    
    def read_training_data(self, limit: int = None) -> list[dict]:
        """
        Read training data synchronously (for analysis/training scripts).
        
        Returns list of all logged entries.
        """
        entries = []
        
        if not os.path.exists(self.filepath):
            return entries
        
        with open(self.filepath, 'r') as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        return entries
    
    def get_decision_feedback_pairs(self) -> list[tuple[dict, list[dict]]]:
        """
        Join decisions with their corresponding feedback.
        
        Returns list of (decision, [feedback, feedback, ...]) tuples.
        Useful for training: context -> weights -> did user like results?
        """
        entries = self.read_training_data()
        
        # Group by request_id
        decisions = {}
        feedback = {}
        
        for entry in entries:
            request_id = entry.get("request_id")
            if entry["type"] == "decision":
                decisions[request_id] = entry
            elif entry["type"] == "feedback":
                if request_id not in feedback:
                    feedback[request_id] = []
                feedback[request_id].append(entry)
        
        # Join
        pairs = []
        for request_id, decision in decisions.items():
            fb = feedback.get(request_id, [])
            pairs.append((decision, fb))
        
        return pairs
