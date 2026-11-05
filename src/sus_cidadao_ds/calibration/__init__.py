"""Calibração científica do limiar de abstenção (`min_score`) no Golden Dataset."""

from sus_cidadao_ds.calibration.threshold_optimizer import (
    CalibrationPoint,
    CalibrationSummary,
    ThresholdCalibrator,
)

__all__ = ["CalibrationPoint", "CalibrationSummary", "ThresholdCalibrator"]

