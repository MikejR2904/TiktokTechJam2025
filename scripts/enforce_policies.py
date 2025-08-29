import pandas as pd
from src.policy.policy_enforcer import PolicyEnforcer

if __name__ == "__main__":
    # Load review data
    df = pd.read_csv("src/data/processed/final_features.csv")
    df = df.head(100)

    # Instantiate enforcer
    enforcer = PolicyEnforcer(use_zero_shot=True)

    # Apply enforcement
    df_enforced = enforcer.enforce(df)

    # Save results
    df_enforced.to_csv("src/data/processed/enforced_reviews.csv", index=False)
    print("✅ Enforcement complete. Output saved to enforced_reviews.csv")
