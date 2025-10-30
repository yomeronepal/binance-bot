"""
ML-Based Tuning Engine

Machine learning engine for automatic strategy parameter tuning.

Supports multiple ML algorithms:
- Random Forest
- Gradient Boosting (XGBoost)
- Bayesian Optimization
- Neural Networks
- Support Vector Regression
"""

import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import random
import logging

logger = logging.getLogger(__name__)


class MLTuningEngine:
    """Engine for ML-based parameter tuning."""

    def __init__(self, ml_algorithm: str = 'GRADIENT_BOOSTING'):
        """
        Initialize ML tuning engine.

        Args:
            ml_algorithm: ML algorithm to use
        """
        self.ml_algorithm = ml_algorithm
        self.model = None
        self.scaler = None
        self.feature_names = []

    def generate_parameter_samples(
        self,
        parameter_space: Dict[str, Dict[str, float]],
        num_samples: int,
        method: str = 'random'
    ) -> List[Dict[str, float]]:
        """
        Generate parameter combinations to test.

        Args:
            parameter_space: Parameter ranges
            num_samples: Number of samples to generate
            method: 'random', 'grid', or 'latin_hypercube'

        Returns:
            List of parameter dictionaries
        """
        samples = []

        if method == 'random':
            # Random sampling
            for _ in range(num_samples):
                sample = {}
                for param_name, bounds in parameter_space.items():
                    min_val = bounds['min']
                    max_val = bounds['max']
                    param_type = bounds.get('type', 'continuous')

                    if param_type == 'integer':
                        sample[param_name] = random.randint(int(min_val), int(max_val))
                    elif param_type == 'discrete':
                        values = bounds.get('values', [])
                        sample[param_name] = random.choice(values)
                    else:  # continuous
                        sample[param_name] = random.uniform(min_val, max_val)

                samples.append(sample)

        elif method == 'latin_hypercube':
            # Latin Hypercube Sampling for better space coverage
            from scipy.stats import qmc

            param_names = list(parameter_space.keys())
            n_params = len(param_names)

            sampler = qmc.LatinHypercube(d=n_params)
            lhs_samples = sampler.random(n=num_samples)

            for sample_array in lhs_samples:
                sample = {}
                for i, param_name in enumerate(param_names):
                    bounds = parameter_space[param_name]
                    min_val = bounds['min']
                    max_val = bounds['max']
                    param_type = bounds.get('type', 'continuous')

                    # Scale from [0, 1] to [min, max]
                    scaled_value = min_val + sample_array[i] * (max_val - min_val)

                    if param_type == 'integer':
                        sample[param_name] = int(round(scaled_value))
                    else:
                        sample[param_name] = scaled_value

                samples.append(sample)

        return samples

    def extract_features(
        self,
        parameters: Dict[str, float],
        market_data: Optional[Dict] = None,
        use_technical_indicators: bool = True,
        use_market_conditions: bool = True,
        use_temporal_features: bool = True
    ) -> Dict[str, float]:
        """
        Extract features from parameters and market data.

        Args:
            parameters: Strategy parameters
            market_data: Optional market data for context features
            use_technical_indicators: Include technical indicator features
            use_market_conditions: Include market condition features
            use_temporal_features: Include time-based features

        Returns:
            Dictionary of feature values
        """
        features = {}

        # 1. Parameter Features (always included)
        for param_name, param_value in parameters.items():
            features[f'param_{param_name}'] = float(param_value)

        # 2. Parameter Interactions
        param_list = list(parameters.values())
        if len(param_list) >= 2:
            features['param_mean'] = np.mean(param_list)
            features['param_std'] = np.std(param_list)
            features['param_range'] = max(param_list) - min(param_list)

            # Pairwise interactions for key parameters
            if 'rsi_oversold' in parameters and 'rsi_overbought' in parameters:
                features['rsi_range'] = parameters['rsi_overbought'] - parameters['rsi_oversold']

            if 'sl_atr_multiplier' in parameters and 'tp_atr_multiplier' in parameters:
                features['risk_reward_ratio'] = parameters['tp_atr_multiplier'] / parameters['sl_atr_multiplier'] if parameters['sl_atr_multiplier'] != 0 else 0

        # 3. Market Condition Features
        if use_market_conditions and market_data:
            if 'volatility' in market_data:
                features['market_volatility'] = market_data['volatility']
            if 'trend_strength' in market_data:
                features['market_trend'] = market_data['trend_strength']
            if 'volume_profile' in market_data:
                features['market_volume'] = market_data['volume_profile']

        # 4. Temporal Features
        if use_temporal_features and market_data:
            if 'timestamp' in market_data:
                dt = market_data['timestamp'] if isinstance(market_data['timestamp'], datetime) else datetime.now()
                features['hour_of_day'] = dt.hour
                features['day_of_week'] = dt.weekday()
                features['day_of_month'] = dt.day

        return features

    def prepare_training_data(
        self,
        samples: List[Dict],
        optimization_metric: str = 'SHARPE_RATIO'
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare training data from samples.

        Args:
            samples: List of sample dictionaries with features and results
            optimization_metric: Metric to optimize

        Returns:
            Tuple of (X, y, feature_names)
        """
        if not samples:
            raise ValueError("No samples provided for training")

        # Convert samples to DataFrame
        df = pd.DataFrame(samples)

        # Extract features (all columns starting with 'param_' or in features dict)
        feature_cols = [col for col in df.columns if col.startswith('param_') or col in ['features']]

        # If features are stored in a dict column, expand them
        if 'features' in df.columns:
            features_df = pd.json_normalize(df['features'])
            df = pd.concat([df, features_df], axis=1)
            feature_cols = list(features_df.columns)

        # Get feature matrix X
        X = df[feature_cols].values

        # Get target variable y based on optimization metric
        metric_mapping = {
            'ROI': 'roi',
            'SHARPE_RATIO': 'sharpe_ratio',
            'PROFIT_FACTOR': 'profit_factor',
            'WIN_RATE': 'win_rate',
            'RISK_ADJUSTED_RETURN': 'risk_adjusted_return'
        }

        target_col = metric_mapping.get(optimization_metric, 'sharpe_ratio')

        if target_col not in df.columns:
            # Calculate risk-adjusted return if not present
            if 'roi' in df.columns and 'max_drawdown' in df.columns:
                df['risk_adjusted_return'] = df['roi'] / (df['max_drawdown'] + 1)  # +1 to avoid division by zero
                target_col = 'risk_adjusted_return'
            else:
                raise ValueError(f"Target column '{target_col}' not found in samples")

        y = df[target_col].values

        feature_names = feature_cols

        return X, y, feature_names

    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        hyperparameters: Optional[Dict] = None
    ) -> Tuple[Any, Any, Dict[str, float]]:
        """
        Train ML model.

        Args:
            X_train: Training features
            y_train: Training targets
            X_val: Validation features (optional)
            y_val: Validation targets (optional)
            hyperparameters: Model hyperparameters

        Returns:
            Tuple of (model, scaler, scores)
        """
        from sklearn.preprocessing import StandardScaler
        from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
        from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val) if X_val is not None else None

        # Initialize model based on algorithm
        if hyperparameters is None:
            hyperparameters = {}

        if self.ml_algorithm == 'RANDOM_FOREST':
            model = RandomForestRegressor(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 10),
                min_samples_split=hyperparameters.get('min_samples_split', 5),
                min_samples_leaf=hyperparameters.get('min_samples_leaf', 2),
                random_state=42,
                n_jobs=-1
            )

        elif self.ml_algorithm == 'GRADIENT_BOOSTING':
            try:
                from xgboost import XGBRegressor
                model = XGBRegressor(
                    n_estimators=hyperparameters.get('n_estimators', 100),
                    max_depth=hyperparameters.get('max_depth', 6),
                    learning_rate=hyperparameters.get('learning_rate', 0.1),
                    subsample=hyperparameters.get('subsample', 0.8),
                    colsample_bytree=hyperparameters.get('colsample_bytree', 0.8),
                    random_state=42,
                    n_jobs=-1
                )
            except ImportError:
                # Fallback to sklearn's GradientBoostingRegressor
                logger.warning("XGBoost not available, using sklearn GradientBoostingRegressor")
                model = GradientBoostingRegressor(
                    n_estimators=hyperparameters.get('n_estimators', 100),
                    max_depth=hyperparameters.get('max_depth', 6),
                    learning_rate=hyperparameters.get('learning_rate', 0.1),
                    subsample=hyperparameters.get('subsample', 0.8),
                    random_state=42
                )

        elif self.ml_algorithm == 'NEURAL_NETWORK':
            from sklearn.neural_network import MLPRegressor
            model = MLPRegressor(
                hidden_layer_sizes=hyperparameters.get('hidden_layer_sizes', (100, 50)),
                activation=hyperparameters.get('activation', 'relu'),
                max_iter=hyperparameters.get('max_iter', 500),
                random_state=42
            )

        elif self.ml_algorithm == 'SVR':
            from sklearn.svm import SVR
            model = SVR(
                kernel=hyperparameters.get('kernel', 'rbf'),
                C=hyperparameters.get('C', 1.0),
                epsilon=hyperparameters.get('epsilon', 0.1)
            )

        else:
            # Default to Gradient Boosting
            model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )

        # Train model
        logger.info(f"Training {self.ml_algorithm} model...")
        model.fit(X_train_scaled, y_train)

        # Calculate scores
        scores = {}

        # Training score
        y_train_pred = model.predict(X_train_scaled)
        scores['train_r2'] = r2_score(y_train, y_train_pred)
        scores['train_mse'] = mean_squared_error(y_train, y_train_pred)
        scores['train_mae'] = mean_absolute_error(y_train, y_train_pred)

        # Validation score
        if X_val is not None and y_val is not None:
            y_val_pred = model.predict(X_val_scaled)
            scores['val_r2'] = r2_score(y_val, y_val_pred)
            scores['val_mse'] = mean_squared_error(y_val, y_val_pred)
            scores['val_mae'] = mean_absolute_error(y_val, y_val_pred)

            # Overfitting score
            scores['overfitting'] = scores['train_r2'] - scores['val_r2']

        self.model = model
        self.scaler = scaler

        return model, scaler, scores

    def predict(
        self,
        parameters: Dict[str, float],
        features: Optional[Dict[str, float]] = None
    ) -> Tuple[float, float]:
        """
        Predict performance for given parameters.

        Args:
            parameters: Strategy parameters
            features: Optional pre-computed features

        Returns:
            Tuple of (predicted_value, confidence)
        """
        if self.model is None or self.scaler is None:
            raise ValueError("Model not trained yet")

        # Extract or use provided features
        if features is None:
            features = self.extract_features(parameters)

        # Convert to array
        feature_values = [features.get(fname, 0) for fname in self.feature_names]
        X = np.array(feature_values).reshape(1, -1)

        # Scale and predict
        X_scaled = self.scaler.transform(X)
        prediction = self.model.predict(X_scaled)[0]

        # Calculate confidence (for tree-based models with estimators)
        confidence = 0.0
        if hasattr(self.model, 'estimators_'):
            # Get predictions from all trees
            predictions = [estimator.predict(X_scaled)[0] for estimator in self.model.estimators_]
            std = np.std(predictions)
            # Convert to confidence score (lower std = higher confidence)
            confidence = max(0, min(100, 100 * (1 - std / (abs(prediction) + 0.01))))
        else:
            confidence = 75.0  # Default confidence for models without ensembles

        return float(prediction), float(confidence)

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from trained model.

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if self.model is None:
            return {}

        importance_dict = {}

        if hasattr(self.model, 'feature_importances_'):
            # Tree-based models
            importances = self.model.feature_importances_
            for fname, importance in zip(self.feature_names, importances):
                importance_dict[fname] = float(importance)

        elif hasattr(self.model, 'coef_'):
            # Linear models
            coefficients = np.abs(self.model.coef_)
            for fname, coef in zip(self.feature_names, coefficients):
                importance_dict[fname] = float(coef)

        # Sort by importance
        importance_dict = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

        return importance_dict

    def calculate_parameter_sensitivity(
        self,
        base_parameters: Dict[str, float],
        parameter_space: Dict[str, Dict[str, float]],
        num_samples: int = 100
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate sensitivity of performance to each parameter.

        Args:
            base_parameters: Base parameter values
            parameter_space: Parameter ranges
            num_samples: Number of samples per parameter

        Returns:
            Dictionary with sensitivity analysis for each parameter
        """
        if self.model is None:
            return {}

        sensitivity = {}

        for param_name in base_parameters.keys():
            if param_name not in parameter_space:
                continue

            bounds = parameter_space[param_name]
            min_val = bounds['min']
            max_val = bounds['max']

            # Generate values across the range
            values = np.linspace(min_val, max_val, num_samples)
            predictions = []

            for value in values:
                # Create test parameters
                test_params = base_parameters.copy()
                test_params[param_name] = value

                # Get prediction
                pred, _ = self.predict(test_params)
                predictions.append(pred)

            # Calculate sensitivity metrics
            sensitivity[param_name] = {
                'mean_prediction': float(np.mean(predictions)),
                'std_prediction': float(np.std(predictions)),
                'min_prediction': float(np.min(predictions)),
                'max_prediction': float(np.max(predictions)),
                'range': float(np.max(predictions) - np.min(predictions)),
                'sensitivity_score': float(np.std(predictions) / (abs(np.mean(predictions)) + 0.01))  # Coefficient of variation
            }

        return sensitivity

    def find_optimal_parameters(
        self,
        parameter_space: Dict[str, Dict[str, float]],
        num_candidates: int = 1000
    ) -> List[Tuple[Dict[str, float], float, float]]:
        """
        Find optimal parameters using trained model.

        Args:
            parameter_space: Parameter ranges to search
            num_candidates: Number of candidates to evaluate

        Returns:
            List of (parameters, predicted_performance, confidence) tuples, sorted by performance
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        # Generate candidate parameters
        candidates = self.generate_parameter_samples(parameter_space, num_candidates, method='latin_hypercube')

        # Evaluate each candidate
        results = []
        for params in candidates:
            try:
                pred, conf = self.predict(params)
                results.append((params, pred, conf))
            except Exception as e:
                logger.warning(f"Failed to predict for params {params}: {e}")
                continue

        # Sort by predicted performance (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def assess_model_quality(
        self,
        scores: Dict[str, float]
    ) -> Tuple[bool, Decimal, str]:
        """
        Assess if model is production-ready.

        Criteria:
        1. Validation R² > 0.5 (explains >50% of variance)
        2. Overfitting < 0.2 (train-val R² difference < 0.2)
        3. Validation MAE is reasonable

        Args:
            scores: Dictionary of model scores

        Returns:
            Tuple of (is_production_ready, quality_score, explanation)
        """
        is_ready = True
        reasons = []
        quality_components = []

        # Criterion 1: Validation R² score
        val_r2 = scores.get('val_r2', 0)
        if val_r2 >= 0.7:
            quality_components.append(30)
            reasons.append(f"✅ Excellent model fit (R²={val_r2:.3f})")
        elif val_r2 >= 0.5:
            quality_components.append(20)
            reasons.append(f"✅ Good model fit (R²={val_r2:.3f})")
        else:
            is_ready = False
            quality_components.append(0)
            reasons.append(f"❌ Poor model fit (R²={val_r2:.3f}, need >0.5)")

        # Criterion 2: Overfitting
        overfitting = scores.get('overfitting', 0)
        if overfitting < 0.1:
            quality_components.append(30)
            reasons.append(f"✅ Minimal overfitting ({overfitting:.3f})")
        elif overfitting < 0.2:
            quality_components.append(20)
            reasons.append(f"⚠️ Moderate overfitting ({overfitting:.3f})")
        else:
            is_ready = False
            quality_components.append(0)
            reasons.append(f"❌ High overfitting ({overfitting:.3f}, need <0.2)")

        # Criterion 3: Training score sanity check
        train_r2 = scores.get('train_r2', 0)
        if train_r2 >= 0.8:
            quality_components.append(20)
            reasons.append(f"✅ Strong training fit (R²={train_r2:.3f})")
        elif train_r2 >= 0.6:
            quality_components.append(10)
            reasons.append(f"⚠️ Moderate training fit (R²={train_r2:.3f})")
        else:
            quality_components.append(0)
            reasons.append(f"⚠️ Weak training fit (R²={train_r2:.3f})")

        # Criterion 4: Error metrics
        val_mae = scores.get('val_mae', float('inf'))
        if val_mae < 5.0:
            quality_components.append(20)
            reasons.append(f"✅ Low prediction error (MAE={val_mae:.2f})")
        elif val_mae < 10.0:
            quality_components.append(10)
            reasons.append(f"⚠️ Moderate prediction error (MAE={val_mae:.2f})")
        else:
            quality_components.append(0)
            reasons.append(f"⚠️ High prediction error (MAE={val_mae:.2f})")

        # Calculate total score
        quality_score = Decimal(str(sum(quality_components)))

        # Overall assessment
        if is_ready and quality_score >= 70:
            reasons.insert(0, "🎯 **PRODUCTION READY** - Model meets quality standards")
        elif quality_score >= 50:
            reasons.insert(0, "⚠️ **USE WITH CAUTION** - Model has moderate quality")
        else:
            reasons.insert(0, "❌ **NOT READY** - Model quality insufficient for production")

        explanation = "\n".join(reasons)

        return is_ready, quality_score, explanation
