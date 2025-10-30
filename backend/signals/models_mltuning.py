"""
ML-Based Tuning Models

Machine Learning-based parameter tuning uses historical data and ML algorithms
to find optimal strategy parameters automatically.

Supported ML Algorithms:
- Random Forest
- Gradient Boosting (XGBoost)
- Bayesian Optimization
- Neural Networks
- Support Vector Regression
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import json

User = get_user_model()


class MLTuningJob(models.Model):
    """
    ML-Based Parameter Tuning Job

    Uses machine learning to automatically find optimal strategy parameters.
    """

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    ML_ALGORITHM_CHOICES = [
        ('RANDOM_FOREST', 'Random Forest'),
        ('GRADIENT_BOOSTING', 'Gradient Boosting (XGBoost)'),
        ('BAYESIAN_OPTIMIZATION', 'Bayesian Optimization'),
        ('NEURAL_NETWORK', 'Neural Network'),
        ('SVR', 'Support Vector Regression'),
        ('ENSEMBLE', 'Ensemble (Multiple Models)'),
    ]

    OPTIMIZATION_METRIC_CHOICES = [
        ('ROI', 'Return on Investment'),
        ('SHARPE_RATIO', 'Sharpe Ratio'),
        ('PROFIT_FACTOR', 'Profit Factor'),
        ('WIN_RATE', 'Win Rate'),
        ('RISK_ADJUSTED_RETURN', 'Risk-Adjusted Return'),
        ('CUSTOM', 'Custom Metric'),
    ]

    # Basic Information
    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='ml_tuning_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    # Training Data Configuration
    symbols = models.JSONField(default=list, help_text="List of trading symbols")
    timeframe = models.CharField(max_length=10, default='5m')
    training_start_date = models.DateTimeField()
    training_end_date = models.DateTimeField()
    validation_start_date = models.DateTimeField(null=True, blank=True, help_text="Optional validation period")
    validation_end_date = models.DateTimeField(null=True, blank=True)

    # ML Configuration
    ml_algorithm = models.CharField(max_length=30, choices=ML_ALGORITHM_CHOICES, default='GRADIENT_BOOSTING')
    optimization_metric = models.CharField(max_length=30, choices=OPTIMIZATION_METRIC_CHOICES, default='SHARPE_RATIO')

    # Parameter Search Space
    parameter_space = models.JSONField(
        default=dict,
        help_text="Parameter ranges to explore (e.g., {'rsi_oversold': {'min': 20, 'max': 40}})"
    )

    # ML Hyperparameters
    ml_hyperparameters = models.JSONField(
        default=dict,
        help_text="ML model hyperparameters (e.g., {'n_estimators': 100, 'max_depth': 10})"
    )

    # Feature Engineering
    use_technical_indicators = models.BooleanField(default=True, help_text="Include technical indicators as features")
    use_market_conditions = models.BooleanField(default=True, help_text="Include market conditions (volatility, trend)")
    use_temporal_features = models.BooleanField(default=True, help_text="Include time-based features (hour, day)")
    custom_features = models.JSONField(default=list, help_text="Custom feature definitions")

    # Training Configuration
    num_training_samples = models.IntegerField(default=1000, help_text="Number of parameter combinations to try")
    train_test_split = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.80'), help_text="Train/test split ratio")
    cross_validation_folds = models.IntegerField(default=5, help_text="Number of CV folds")

    # Capital Configuration
    initial_capital = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('10000.00'))
    position_size = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('100.00'))

    # Results - Best Parameters
    best_parameters = models.JSONField(default=dict, help_text="Optimal parameters found by ML")
    predicted_performance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="ML model's predicted performance"
    )

    # Results - Training Performance
    training_score = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), help_text="R² score on training set")
    validation_score = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), help_text="R² score on validation set")
    test_score = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), help_text="R² score on test set")

    # Results - Out-of-Sample Verification
    out_of_sample_roi = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Actual ROI on validation period"
    )
    out_of_sample_sharpe = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    out_of_sample_win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    out_of_sample_max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Model Explainability
    feature_importance = models.JSONField(
        default=dict,
        help_text="Feature importance scores from ML model"
    )
    parameter_sensitivity = models.JSONField(
        default=dict,
        help_text="How sensitive performance is to each parameter"
    )

    # Model Artifacts
    model_file_path = models.CharField(max_length=500, blank=True, help_text="Path to saved model file")
    scaler_file_path = models.CharField(max_length=500, blank=True, help_text="Path to saved scaler file")

    # Execution Tracking
    samples_evaluated = models.IntegerField(default=0)
    samples_successful = models.IntegerField(default=0)
    samples_failed = models.IntegerField(default=0)

    # Quality Metrics
    overfitting_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Difference between training and validation performance"
    )
    model_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Model's confidence in predictions (0-100)"
    )
    is_production_ready = models.BooleanField(default=False, help_text="Passes quality checks for production use")

    # Task Management
    task_id = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ml_tuning_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['ml_algorithm']),
            models.Index(fields=['is_production_ready']),
        ]

    def __str__(self):
        return f"ML Tuning #{self.id}: {self.name} ({self.ml_algorithm})"

    def execution_time_seconds(self):
        """Calculate execution time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def progress_percentage(self):
        """Calculate progress percentage."""
        if self.num_training_samples > 0:
            return int((self.samples_evaluated / self.num_training_samples) * 100)
        return 0


class MLTuningSample(models.Model):
    """
    Individual ML Training Sample

    Stores results from testing a specific parameter combination.
    """

    tuning_job = models.ForeignKey(MLTuningJob, on_delete=models.CASCADE, related_name='samples')
    sample_number = models.IntegerField(help_text="Sample number (1 to N)")

    # Parameters Tested
    parameters = models.JSONField(default=dict, help_text="Parameters tested in this sample")

    # Features Extracted
    features = models.JSONField(default=dict, help_text="Feature values for this sample")

    # Performance Results
    roi = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    sharpe_ratio = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    profit_factor = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_trades = models.IntegerField(default=0)

    # Target Value (what ML model predicts)
    target_value = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text="The optimization metric value (what ML predicts)"
    )

    # Data Split Assignment
    split_set = models.CharField(
        max_length=10,
        choices=[('TRAIN', 'Training'), ('TEST', 'Testing'), ('VALIDATION', 'Validation')],
        default='TRAIN'
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'ml_tuning_samples'
        ordering = ['sample_number']
        indexes = [
            models.Index(fields=['tuning_job', 'sample_number']),
            models.Index(fields=['tuning_job', 'split_set']),
            models.Index(fields=['tuning_job', 'target_value']),
        ]

    def __str__(self):
        return f"ML Sample #{self.sample_number} (Job {self.tuning_job.id}): Target {self.target_value}"


class MLPrediction(models.Model):
    """
    ML Model Predictions

    Stores predictions made by the trained ML model.
    """

    tuning_job = models.ForeignKey(MLTuningJob, on_delete=models.CASCADE, related_name='predictions')

    # Input Parameters
    parameters = models.JSONField(default=dict, help_text="Parameters for which prediction was made")

    # Features Used
    features = models.JSONField(default=dict, help_text="Feature values used for prediction")

    # Prediction
    predicted_value = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text="ML model's predicted performance"
    )
    prediction_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Model's confidence in this prediction"
    )

    # Actual Results (if available)
    actual_value = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Actual performance observed"
    )
    prediction_error = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Difference between predicted and actual"
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True, help_text="When actual value was verified")

    class Meta:
        db_table = 'ml_predictions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tuning_job', 'created_at']),
            models.Index(fields=['tuning_job', 'predicted_value']),
        ]

    def __str__(self):
        return f"ML Prediction (Job {self.tuning_job.id}): {self.predicted_value}"


class MLModel(models.Model):
    """
    Trained ML Model Metadata

    Stores information about trained ML models for reuse.
    """

    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='ml_models')
    tuning_job = models.ForeignKey(
        MLTuningJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Original tuning job that created this model"
    )

    # Model Configuration
    ml_algorithm = models.CharField(max_length=30)
    optimization_metric = models.CharField(max_length=30)
    feature_set = models.JSONField(default=list, help_text="List of features used")

    # Model Performance
    training_score = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    validation_score = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    test_score = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))

    # Model Files
    model_file_path = models.CharField(max_length=500)
    scaler_file_path = models.CharField(max_length=500, blank=True)
    metadata_file_path = models.CharField(max_length=500, blank=True)

    # Usage Tracking
    times_used = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_production_ready = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ml_models'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['ml_algorithm']),
            models.Index(fields=['is_production_ready']),
        ]

    def __str__(self):
        return f"ML Model: {self.name} ({self.ml_algorithm})"
