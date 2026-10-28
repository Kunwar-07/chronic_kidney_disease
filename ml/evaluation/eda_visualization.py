
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import joblib
import shap
import json
import os
import sys
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.pipeline import NUMERIC_FEATURES, CATEGORICAL_FEATURES, ALL_FEATURES
from sklearn.metrics import roc_curve, roc_auc_score
from sklearn.model_selection import train_test_split

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH  = os.path.join(BASE_DIR, "data", "processed", "ckd_cleaned.csv")
ART_DIR    = os.path.join(BASE_DIR, "artifacts")
PLOTS_DIR  = os.path.join(ART_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

PALETTE = {"No CKD": "#4CC9F0", "CKD": "#F72585"}
DARK_BG = "#0f1117"
CARD_BG = "#1a1d27"
TEXT    = "#e0e0e0"
ACCENT  = "#7B5CF6"

# Shared seaborn theme
sns.set_theme(style="darkgrid", palette="muted")
plt.rcParams.update({
    "figure.facecolor": DARK_BG,
    "axes.facecolor":   CARD_BG,
    "axes.edgecolor":   "#333",
    "axes.labelcolor":  TEXT,
    "xtick.color":      TEXT,
    "ytick.color":      TEXT,
    "text.color":       TEXT,
    "grid.color":       "#2a2d3a",
    "font.family":      "DejaVu Sans",
})

def load_data():
    df = pd.read_csv(DATA_PATH)
    df["ckd_label"] = df["target"].map({1: "CKD", 0: "No CKD"})
    X = df[ALL_FEATURES]
    y = df["target"]
    return df, X, y

def save(name):
    path = os.path.join(PLOTS_DIR, name)
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  [OK] Saved: {path}")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Class Distribution
# ─────────────────────────────────────────────────────────────────────────────
def plot_class_distribution(df):
    counts = df["ckd_label"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 5), facecolor=DARK_BG)
    bars = ax.bar(counts.index, counts.values,
                  color=[PALETTE["CKD"], PALETTE["No CKD"]], width=0.5, edgecolor="none")
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                f"{val:,}", ha="center", va="bottom", fontsize=12, color=TEXT, fontweight="bold")
    ax.set_title("CKD Class Distribution", fontsize=16, color=TEXT, pad=14)
    ax.set_ylabel("Number of Patients", fontsize=12)
    ax.set_xlabel("")
    ax.set_facecolor(CARD_BG)
    for spine in ax.spines.values(): spine.set_visible(False)
    save("01_class_distribution.png")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Correlation Heatmap
# ─────────────────────────────────────────────────────────────────────────────
def plot_correlation_heatmap(df):
    num_df = df[NUMERIC_FEATURES + ["target"]].copy()
    corr = num_df.corr()
    fig, ax = plt.subplots(figsize=(14, 11), facecolor=DARK_BG)
    mask = np.triu(np.ones_like(corr, dtype=bool))
    cmap = sns.diverging_palette(220, 20, as_cmap=True)
    sns.heatmap(corr, mask=mask, cmap=cmap, center=0, vmin=-1, vmax=1,
                annot=True, fmt=".2f", linewidths=0.4, linecolor="#1a1d27",
                ax=ax, cbar_kws={"shrink": 0.8, "label": "Pearson r"},
                annot_kws={"size": 7})
    ax.set_title("Numeric Feature Correlation Heatmap", fontsize=16, color=TEXT, pad=14)
    ax.set_facecolor(CARD_BG)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(rotation=0, fontsize=8)
    save("02_correlation_heatmap.png")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Violin Plots: Feature Distribution by CKD Status
# ─────────────────────────────────────────────────────────────────────────────
def plot_violin_distributions(df):
    features = [f for f in NUMERIC_FEATURES if df[f].notna().sum() > 100]
    n_cols = 3
    n_rows = int(np.ceil(len(features) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, n_rows * 3.5), facecolor=DARK_BG)
    axes = axes.flatten()
    for i, feat in enumerate(features):
        ax = axes[i]
        plot_df = df[[feat, "ckd_label"]].dropna()
        sns.violinplot(data=plot_df, x="ckd_label", y=feat, ax=ax,
                       palette=PALETTE, inner="quartile", linewidth=1.2)
        ax.set_title(feat.replace("_", " ").title(), fontsize=9, color=TEXT)
        ax.set_xlabel(""); ax.set_ylabel("")
        ax.set_facecolor(CARD_BG)
        for spine in ax.spines.values(): spine.set_color("#333")
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)
    fig.suptitle("Feature Distributions by CKD Status", fontsize=16, color=TEXT, y=1.01)
    plt.tight_layout()
    save("03_violin_distributions.png")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Missing Value Heatmap
# ─────────────────────────────────────────────────────────────────────────────
def plot_missing_values(df):
    missing = df[ALL_FEATURES].isnull().mean().sort_values(ascending=False)
    missing = missing[missing > 0]
    if missing.empty:
        print("  (No missing values to plot — skipping.)")
        return
    fig, ax = plt.subplots(figsize=(10, max(4, len(missing) * 0.35)), facecolor=DARK_BG)
    bars = ax.barh(missing.index[::-1], missing.values[::-1] * 100,
                   color=ACCENT, edgecolor="none")
    for bar, val in zip(bars, missing.values[::-1] * 100):
        ax.text(val + 0.3, bar.get_y() + bar.get_height()/2,
                f"{val:.1f}%", va="center", fontsize=8, color=TEXT)
    ax.set_xlabel("Missing (%)", fontsize=11)
    ax.set_title("Missing Values per Feature", fontsize=15, color=TEXT, pad=12)
    ax.set_facecolor(CARD_BG)
    for spine in ax.spines.values(): spine.set_visible(False)
    plt.tight_layout()
    save("04_missing_values.png")

# ─────────────────────────────────────────────────────────────────────────────
# 5. ROC-AUC Curves for Stacking Model
# ─────────────────────────────────────────────────────────────────────────────
def plot_roc_curves(X, y):
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    fig, ax = plt.subplots(figsize=(8, 6), facecolor=DARK_BG)
    
    model_path = os.path.join(ART_DIR, "stacking_ckd_model.pkl")
    if os.path.exists(model_path):
        pipeline = joblib.load(model_path)
        y_prob = pipeline.predict_proba(X_test)[:, 1]
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        auc = roc_auc_score(y_test, y_prob)
        ax.plot(fpr, tpr, color="#F72585", lw=2.2, label=f"STACKING ENSEMBLE (AUC = {auc:.3f})")
    else:
        print("  ! Stacking model not found, skipping ROC.")
        
    ax.plot([0, 1], [0, 1], "--", color="#555", lw=1.2, label="Random Baseline")
    ax.fill_between([0, 1], [0, 1], alpha=0.04, color="#555")
    ax.set_xlim([0, 1]); ax.set_ylim([0, 1.01])
    ax.set_xlabel("False Positive Rate", fontsize=12)
    ax.set_ylabel("True Positive Rate", fontsize=12)
    ax.set_title("ROC-AUC Curve — Stacking Ensemble", fontsize=15, color=TEXT, pad=12)
    ax.set_facecolor(CARD_BG)
    legend = ax.legend(fontsize=10, facecolor=DARK_BG, edgecolor="#333", labelcolor=TEXT)
    for spine in ax.spines.values(): spine.set_color("#333")
    plt.tight_layout()
    save("05_roc_auc_curves.png")

# ─────────────────────────────────────────────────────────────────────────────
# 6. SHAP Global Feature Importance (Stacking Ensemble)
# ─────────────────────────────────────────────────────────────────────────────
def plot_shap_importance(X):
    model_path = os.path.join(ART_DIR, "stacking_ckd_model.pkl")
    if not os.path.exists(model_path):
        print("  ! Stacking model not found — skipping SHAP plot.")
        return
        
    pipeline = joblib.load(model_path)
    preprocessor = pipeline[:-2]
    model = pipeline.named_steps["model"]
    
    sample = X.dropna().sample(min(200, len(X.dropna())), random_state=42)
    X_t = preprocessor.transform(sample)
    if hasattr(X_t, "toarray"): X_t = X_t.toarray()
    
    from preprocessing.pipeline import get_feature_names
    feature_names = get_feature_names(preprocessor)
    
    all_sv = []
    for est in model.estimators_:
        explainer = shap.TreeExplainer(est)
        shap_vals = explainer.shap_values(X_t)
        
        # Robust SHAP array extraction
        if isinstance(shap_vals, list):
            sv = shap_vals[1]
            if len(sv.shape) == 3: sv = sv[:, :, 1]
        elif shap_vals.ndim == 3:
            sv = shap_vals[:, :, 1]
        else:
            sv = shap_vals
            
        all_sv.append(sv)
        
    # Average across base estimators, then take absolute mean across samples
    avg_sv = np.mean(all_sv, axis=0)
    mean_shap = np.abs(avg_sv).mean(axis=0)
    
    importance_df = pd.DataFrame({"feature": feature_names, "importance": mean_shap})
    importance_df = importance_df.sort_values("importance", ascending=True).tail(15)
    
    fig, ax = plt.subplots(figsize=(10, 7), facecolor=DARK_BG)
    colors = plt.cm.plasma(np.linspace(0.3, 0.9, len(importance_df)))
    ax.barh(importance_df["feature"], importance_df["importance"], color=colors, edgecolor="none")
    ax.set_xlabel("Mean |SHAP Value|", fontsize=12)
    ax.set_title("Global Feature Importance (Stacking Ensemble)", fontsize=15, color=TEXT, pad=12)
    ax.set_facecolor(CARD_BG)
    for spine in ax.spines.values(): spine.set_visible(False)
    plt.tight_layout()
    save("06_shap_global_importance.png")

# ─────────────────────────────────────────────────────────────────────────────
# 7. Model Comparison Chart
# ─────────────────────────────────────────────────────────────────────────────
def plot_model_comparison():
    metrics_path = os.path.join(ART_DIR, "evaluation_metrics.json")
    if not os.path.exists(metrics_path):
        print("  ! evaluation_metrics.json not found — skipping model comparison plot.")
        return
    with open(metrics_path) as f:
        metrics = json.load(f)
        
    # Just plot whatever models are in the JSON
    models = [m for m in metrics.keys() if m != "_note"]
    if not models:
        return
        
    accuracy = [metrics[m]["accuracy"] * 100 for m in models]
    roc_auc  = [metrics[m]["roc_auc"]  * 100 for m in models]
    x = np.arange(len(models))
    width = 0.35
    fig, ax = plt.subplots(figsize=(max(6, len(models)*2), 6), facecolor=DARK_BG)
    bars1 = ax.bar(x - width/2, accuracy, width, label="Accuracy (%)", color="#4CC9F0", edgecolor="none")
    bars2 = ax.bar(x + width/2, roc_auc,  width, label="ROC-AUC (%)", color="#F72585", edgecolor="none")
    for bar in list(bars1) + list(bars2):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=9, color=TEXT)
    ax.set_ylim(60, 102)
    ax.set_xticks(x); ax.set_xticklabels([m.replace("_", " ").title() for m in models], fontsize=12)
    ax.set_ylabel("Score (%)", fontsize=12)
    ax.set_title("Model Performance Comparison (Test Set)", fontsize=15, color=TEXT, pad=12)
    ax.set_facecolor(CARD_BG)
    ax.legend(facecolor=DARK_BG, edgecolor="#333", labelcolor=TEXT)
    for spine in ax.spines.values(): spine.set_visible(False)
    plt.tight_layout()
    save("07_model_comparison.png")

# ─────────────────────────────────────────────────────────────────────────────
# 8. Scatter: Age vs Blood Urea Nitrogen by CKD Status
# ─────────────────────────────────────────────────────────────────────────────
def plot_scatter_age_bun(df):
    plot_df = df[["age", "blood_urea_nitrogen", "ckd_label"]].dropna()
    fig, ax = plt.subplots(figsize=(9, 6), facecolor=DARK_BG)
    for label, color in PALETTE.items():
        sub = plot_df[plot_df["ckd_label"] == label]
        ax.scatter(sub["age"], sub["blood_urea_nitrogen"], c=color, alpha=0.45,
                   s=18, label=label, edgecolors="none")
    ax.set_xlabel("Age (years)", fontsize=12)
    ax.set_ylabel("Blood Urea Nitrogen (mg/dL)", fontsize=12)
    ax.set_title("Age vs. Blood Urea Nitrogen by CKD Status", fontsize=15, color=TEXT, pad=12)
    ax.set_facecolor(CARD_BG)
    ax.legend(facecolor=DARK_BG, edgecolor="#333", labelcolor=TEXT, markerscale=1.8)
    for spine in ax.spines.values(): spine.set_color("#333")
    plt.tight_layout()
    save("08_age_vs_bun_scatter.png")



# ─────────────────────────────────────────────────────────────────────────────
# 9. Confusion Matrices
# ─────────────────────────────────────────────────────────────────────────────
def plot_confusion_matrices(X, y):
    from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    fig, ax = plt.subplots(1, 1, figsize=(6, 5), facecolor=DARK_BG)
    model_path = os.path.join(ART_DIR, "stacking_ckd_model.pkl")
    
    if os.path.exists(model_path):
        pipeline = joblib.load(model_path)
        y_pred = pipeline.predict(X_test)
        cm = confusion_matrix(y_test, y_pred)
        disp = ConfusionMatrixDisplay(cm, display_labels=["No CKD", "CKD"])
        disp.plot(ax=ax, colorbar=False, cmap="Blues")
        ax.set_facecolor(CARD_BG)
        ax.set_title("STACKING ENSEMBLE", fontsize=13, color=TEXT, pad=10)
        ax.xaxis.label.set_color(TEXT)
        ax.yaxis.label.set_color(TEXT)
        ax.tick_params(colors=TEXT)
        for text in ax.texts:
            text.set_color(TEXT)
            text.set_fontsize(13)
        for spine in ax.spines.values():
            spine.set_color("#333")
    else:
        ax.set_visible(False)
        
    fig.suptitle("Confusion Matrix", fontsize=16, color=TEXT, y=1.02)
    plt.tight_layout()
    save("09_confusion_matrices.png")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Loading data from {DATA_PATH}...")
    df, X, y = load_data()
    print(f"Dataset: {df.shape[0]:,} rows x {df.shape[1]} columns\n")

    print("[1/9] Class distribution...")
    plot_class_distribution(df)

    print("[2/9] Correlation heatmap...")
    plot_correlation_heatmap(df)

    print("[3/9] Violin distributions...")
    plot_violin_distributions(df)

    print("[4/9] Missing values...")
    plot_missing_values(df)

    print("[5/9] ROC-AUC curves...")
    plot_roc_curves(X, y)

    print("[6/9] SHAP global importance...")
    plot_shap_importance(X)

    print("[7/9] Model comparison...")
    plot_model_comparison()

    print("[8/9] Age vs BUN scatter...")
    plot_scatter_age_bun(df)

    print("[9/9] Confusion matrices...")
    plot_confusion_matrices(X, y)

    print(f"\n[DONE] All 9 plots saved to: {PLOTS_DIR}")
