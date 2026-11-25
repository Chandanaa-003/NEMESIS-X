from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BehaviorAnomalyWeights(BaseModel):
    """Normalized weights for the existing explainable anomaly score components."""

    model_config = ConfigDict(extra="forbid")

    duration: float = Field(default=0.15, ge=0, le=1)
    movement_change: float = Field(default=0.25, ge=0, le=1)
    interaction_sequence: float = Field(default=0.25, ge=0, le=1)
    repeated_behavior: float = Field(default=0.15, ge=0, le=1)
    zone_rule: float = Field(default=0.20, ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> "BehaviorAnomalyWeights":
        if abs(sum(self.model_dump().values()) - 1.0) > 1e-6:
            raise ValueError("Anomaly weights must sum to 1.")
        return self


class BehaviorBaselineConfig(BaseModel):
    """Descriptive baseline thresholds scoped to a single monitoring session."""

    model_config = ConfigDict(extra="forbid")

    minimum_tracks: int = Field(default=3, ge=1, le=100)
    minimum_history_seconds: float = Field(default=30.0, gt=0, le=86400)
    stationary_displacement_threshold: float = Field(default=0.04, ge=0, le=1)
    low_movement_speed_threshold: float = Field(default=0.02, ge=0, le=10)
    running_like_speed_threshold: float = Field(default=0.22, ge=0, le=10)
    prolonged_stationary_seconds: float = Field(default=8.0, ge=0, le=86400)
    anomaly_weights: BehaviorAnomalyWeights = Field(default_factory=BehaviorAnomalyWeights)

    @model_validator(mode="after")
    def validate_movement_thresholds(self) -> "BehaviorBaselineConfig":
        if self.running_like_speed_threshold < self.low_movement_speed_threshold:
            raise ValueError(
                "running_like_speed_threshold must be at least low_movement_speed_threshold."
            )
        return self


class BehaviorReportResponse(BaseModel):
    """Behavior report derived from tracked trajectories and persisted events."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    generated_at: str
    summary: dict[str, Any]
    baseline: dict[str, Any]
    movement_summaries: list[dict[str, Any]]
    sequences: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    event_correlations: list[dict[str, Any]]
    scoring_logic: dict[str, Any]
