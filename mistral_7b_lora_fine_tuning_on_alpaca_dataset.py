# -*- coding: utf-8 -*-
"""Mistral_7B_LoRA_Fine_tuning_on_Alpaca_Dataset.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/github/faizan-codes/fine-tuned-models/blob/main/Mistral_7B_LoRA_Fine_tuning_on_Alpaca_Dataset.ipynb

# Mistral-7B LoRA Fine-tuning on Alpaca Dataset - Complete Implementation
# This notebook provides a complete setup for fine-tuning Mistral-7B using LoRA on 1% of the Alpaca dataset
"""

# Step 1: Install Required Libraries
print("Step 1: Installing required libraries...")
!pip install -qU transformers
!pip install -qU peft
!pip install -qU datasets
!pip install -qU accelerate
!pip install -qU bitsandbytes
!pip install -qU trl
!pip install -qU wandb
!pip install -qU torch torchvision torchaudio

# Step 2: Import Libraries
print("Step 2: Importing libraries...")
import torch
import torch.nn as nn
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, TaskType, PeftModel
from datasets import load_dataset
import numpy as np
from trl import SFTTrainer
import warnings
warnings.filterwarnings('ignore')

# Step 3: Check GPU and Setup
print("Step 3: Checking GPU availability...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

# Step 4: Configuration
print("Step 4: Setting up configuration...")
MODEL_NAME = "mistralai/Mistral-7B-v0.1"
DATASET_NAME = "tatsu-lab/alpaca"
OUTPUT_DIR = "./mistral-7b-alpaca-lora"
DATASET_SIZE = 0.01  # 1% of the dataset

# LoRA Configuration
lora_config = LoraConfig(
    r=16,                    # Rank - lower means fewer parameters
    lora_alpha=32,          # LoRA scaling parameter
    target_modules=[        # Which modules to apply LoRA to
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
        "lm_head"
    ],
    lora_dropout=0.1,       # Dropout for LoRA layers
    bias="none",            # No bias terms
    task_type=TaskType.CAUSAL_LM,
)

# Quantization Configuration for memory efficiency
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)

# Step 5: Load and Prepare Dataset
print("Step 5: Loading and preparing dataset...")
dataset = load_dataset(DATASET_NAME)
print(f"Original dataset size: {len(dataset['train'])}")

# Take 1% of the dataset
train_size = int(len(dataset['train']) * DATASET_SIZE)
train_dataset = dataset['train'].select(range(train_size))
print(f"Using {train_size} samples for training")

# Step 6: Format Dataset for Instruction Following
print("Step 6: Formatting dataset...")
def format_instruction(example):
    """Format the Alpaca dataset for instruction following"""
    instruction = example['instruction']
    input_text = example['input']
    output = example['output']

    if input_text:
        prompt = f"Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.\n\n### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n{output}"
    else:
        prompt = f"Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n### Instruction:\n{instruction}\n\n### Response:\n{output}"

    return {"text": prompt}

# Apply formatting
formatted_dataset = train_dataset.map(format_instruction, remove_columns=train_dataset.column_names)
print("Dataset formatted successfully!")

# Step 7: Load Tokenizer
print("Step 7: Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token  # Set padding token
tokenizer.padding_side = "right"  # Fix padding side

# Step 8: Load Model with Quantization
print("Step 8: Loading model with quantization...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
    torch_dtype=torch.bfloat16
)

# Enable gradient checkpointing for memory efficiency
model.gradient_checkpointing_enable()

# Step 9: Apply LoRA
print("Step 9: Applying LoRA configuration...")
model = get_peft_model(model, lora_config)

# Print trainable parameters
trainable_params = 0
all_param = 0
for _, param in model.named_parameters():
    all_param += param.numel()
    if param.requires_grad:
        trainable_params += param.numel()

print(f"Trainable params: {trainable_params:,} || All params: {all_param:,} || Trainable%: {100 * trainable_params / all_param:.4f}")

# Step 10: Training Arguments
print("Step 10: Setting up training arguments...")
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    optim="paged_adamw_32bit",
    save_steps=100,
    logging_steps=25,
    learning_rate=2e-4,
    weight_decay=0.001,
    fp16=False,
    bf16=True,
    max_grad_norm=0.3,
    max_steps=-1,
    warmup_ratio=0.03,
    group_by_length=True,
    lr_scheduler_type="constant",
    report_to="tensorboard",
    save_strategy="steps",
    save_total_limit=3,
    push_to_hub=False,
    disable_tqdm=False,
    remove_unused_columns=False,
    dataloader_pin_memory=False,
    label_names=["labels"]
)

trainer = SFTTrainer(
    model=model,
    train_dataset=formatted_dataset,
    peft_config=lora_config,
    args=training_args,
    # packing=False,
)

# Step 12: Start Training
print("Step 12: Starting training...")
print("This may take some time depending on your GPU...")
trainer.train()

# Step 13: Save the Fine-tuned Model
print("Step 13: Saving the fine-tuned model...")
trainer.model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"Model saved to {OUTPUT_DIR}")

# Step 14: Test the Fine-tuned Model
print("Step 14: Testing the fine-tuned model...")

# Load the fine-tuned model for inference
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
    torch_dtype=torch.bfloat16
)

# Load the LoRA adapter
model = PeftModel.from_pretrained(base_model, OUTPUT_DIR)

def generate_response(instruction, input_text="", max_length=256):
    """Generate response using the fine-tuned model"""
    if input_text:
        prompt = f"Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.\n\n### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n"
    else:
        prompt = f"Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n### Instruction:\n{instruction}\n\n### Response:\n"

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, padding=True).to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_length,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            top_p=0.9,
            repetition_penalty=1.1
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Extract only the response part
    response = response.split("### Response:")[-1].strip()
    return response

# Test with sample instructions
test_instructions = [
    "Explain the concept of artificial intelligence in simple terms.",
    "Write a short poem about nature.",
    "What are the benefits of exercise?"
]

print("\n" + "="*50)
print("TESTING THE FINE-TUNED MODEL")
print("="*50)

for i, instruction in enumerate(test_instructions, 1):
    print(f"\nTest {i}:")
    print(f"Instruction: {instruction}")
    response = generate_response(instruction)
    print(f"Response: {response}")
    print("-" * 30)

# Step 15: Optional - Save to Google Drive
print("\nStep 15: Optional - Save to Google Drive")
print("Uncomment the following lines to save the model to Google Drive:")
print("""
# from google.colab import drive
# drive.mount('/content/drive')
#
# import shutil
# shutil.copytree(OUTPUT_DIR, '/content/drive/MyDrive/mistral-7b-alpaca-lora')
# print("Model saved to Google Drive!")
""")

print("\n" + "="*50)
print("FINE-TUNING COMPLETE!")
print("="*50)
print(f"Model saved to: {OUTPUT_DIR}")
print("You can now use this model for inference or further training.")
print("The model has been fine-tuned on 5% of the Alpaca dataset using LoRA.")