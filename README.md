# Context-Enriched Moderation Engine — TikTok Tech Jam 2025

## 🧠 Project Overview

This project tackles the challenge of evaluating the quality and relevance of location-based reviews by building a hybrid moderation engine that blends rule-based logic, transformer-based NLP, and real-time context enrichment via external APIs. Our engine flags irrelevant, speculative, or emotionally charged reviews and suggests respectful rewrites using retrieval-augmented generation (RAG).

## 🎯 Problem Statement

From the TikTok Tech Jam 2025 challenge prompt:  
**"Design a system that can assess the quality and relevance of user-generated reviews for local businesses, minimizing speculative or emotionally biased content while preserving useful feedback."**

## 💡 Solution Highlights

- **Semantic & Emotional Classification**: Hugging Face zero-shot models detect irrelevant, speculative, or emotionally charged reviews.
- **Contextual Enrichment**: Google Maps and Places APIs fetch business metadata and nearby reviews to provide context for moderation decisions.
- **Respectful Rewrite Module**: Flagged reviews are rewritten using OpenAI GPT-4o and RAG pipelines to preserve intent while improving tone.
- **Rule-Based Enforcement**: Explicit logic modules handle edge cases and ensure policy compliance.
- **Performance Optimization**: Smart batching and caching allow efficient inference on CPU environments.

## 🛠️ Development Tools

- VSCode (primary IDE)
- Jupyter Notebooks (model prototyping)
- Google Colab (GPU-based experimentation)

## 🔌 APIs Used

- Google Maps API
- Google Places API
- OpenAI GPT-4o

## 📚 Libraries & Frameworks

- Hugging Face Transformers
- PyTorch
- scikit-learn
- pandas
- NumPy
- requests
- tqdm

## 📦 Assets & Datasets

- Google Local Reviews dataset (via Places API)
- Manually labeled review samples
- Business metadata (location, category, rating)

## 📁 Directory Structure
documents/tiktoktechjam2025/
├── data/ # Sample reviews + business metadata
├── notebooks/ # Prototyping, model experiments
├── src/ # Core moderation engine + enrichment modules
├── configs/ # Rule definitions + model parameters
└── README.md # You're here

## ⚙️ Setup Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/tiktoktechjam2025.git
   cd tiktoktechjam2025

2. Install dependencies:
    ```bash
    pip install -r requirements.txt

3. Create a .env file in the root of the directory and configure API keys.

4. Run the moderation pipeline:
    ```bash
    uvicorn src.api.app:app --reload




