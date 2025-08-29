from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments

def load_model(model_name="distilbert-base-uncased", num_labels=2):
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=num_labels)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    return model, tokenizer