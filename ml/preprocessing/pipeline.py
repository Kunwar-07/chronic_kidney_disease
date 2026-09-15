"""
pipeline.py
-----------
Builds the reusable sklearn preprocessing pipeline for the NHANES dataset.

Numeric features -> median imputation + standard scaling
Binary/categorical features -> most-frequent imputation + one-hot encoding
"""

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.feature_selection import SelectKBest, f_classif

NUMERIC_FEATURES = [
    "age", "poverty_income_ratio", "bmi", "weight_kg", "height_cm", 
    "bp_systolic", "bp_diastolic", "blood_urea_nitrogen", 
    "albumin_serum", "phosphorus", "bicarbonate", "calcium", "uric_acid", 
    "urine_creatinine"
]

CATEGORICAL_FEATURES = [
    "gender", "ethnicity", "education_level", "diabetes_diagnosed", 
    "insulin_use", "diabetes_pills", "ever_smoked", "current_smoker"
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def build_preprocessing_pipeline() -> Pipeline:
    numeric_transformer = Pipeline(steps=[
        ("imputer", KNNImputer(n_neighbors=5)),
        ("scaler", StandardScaler()),
    ])

    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_FEATURES),
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
        ]
    )
    
    # Wrap in a pipeline to include SelectKBest for top 30 features
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("selector", SelectKBest(score_func=f_classif, k=30))
    ])
    
    return pipeline


def get_feature_names(pipeline: Pipeline) -> list:
    """Return human-readable output feature names after transformation and selection."""
    num_names = NUMERIC_FEATURES
    
    preprocessor = pipeline.named_steps["preprocessor"]
    cat_encoder = preprocessor.named_transformers_["cat"].named_steps["onehot"]
    cat_names = list(cat_encoder.get_feature_names_out(CATEGORICAL_FEATURES))
    
    all_names = num_names + cat_names
    
    # Get the boolean mask from SelectKBest
    selector = pipeline.named_steps["selector"]
    mask = selector.get_support()
    
    selected_names = [name for name, is_selected in zip(all_names, mask) if is_selected]
    return selected_names
