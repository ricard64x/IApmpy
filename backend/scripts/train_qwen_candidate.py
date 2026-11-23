#!/usr/bin/env python3
"""Optional offline LoRA adapter training. Never deploys a candidate.

Requires a separate authorized CUDA training machine and approved JSONL data.
Do not feed raw news, personal records, credentials, synthetic incidents or
unreviewed conversation history into model weights.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def training_rows(path):
    rows=[]
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        row=json.loads(raw)
        if not isinstance(row,dict) or row.get("approved_for_training") is not True:
            continue
        question=row.get("instruction")
        response=row.get("response")
        if (isinstance(question,str) and isinstance(response,str)
            and 10<=len(question)<=1200 and 10<=len(response)<=2400):
            rows.append({"text":"### Instrucción\n"+question+"\n### Respuesta\n"+response})
        if len(rows)>=5000:break
    if len(rows)<100:
        raise ValueError("Se necesitan al menos 100 ejemplos revisados y aprobados")
    return rows

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--approved-data",required=True)
    p.add_argument("--local-base-model",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    base=Path(args.local_base_model)
    output=Path(args.output)
    if not base.is_dir() or output.exists():
        raise ValueError("Modelo base local inexistente o destino ya utilizado")
    rows=training_rows(args.approved_data)
    # Imports are optional: the 2 GB production VM MUST NOT install a GPU stack.
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Entrenamiento no disponible sin GPU CUDA")
    memory=torch.cuda.get_device_properties(0).total_memory
    if memory<8*1024**3:
        raise RuntimeError("GPU insuficiente para entrenar con seguridad")
    from datasets import Dataset
    from peft import LoraConfig,get_peft_model
    from transformers import AutoModelForCausalLM,AutoTokenizer,TrainingArguments,Trainer,DataCollatorForLanguageModeling
    from sklearn.model_selection import train_test_split
    train,_heldout=train_test_split(rows,test_size=.2,random_state=23)
    tokenizer=AutoTokenizer.from_pretrained(str(base),trust_remote_code=False,local_files_only=True)
    if tokenizer.pad_token is None:tokenizer.pad_token=tokenizer.eos_token
    model=AutoModelForCausalLM.from_pretrained(str(base),local_files_only=True,
                                               trust_remote_code=False,torch_dtype=torch.float16)
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=.05,bias="none",
                                        task_type="CAUSAL_LM",target_modules=["q_proj","v_proj"]))
    def tokenize(batch):
        return tokenizer(batch["text"],truncation=True,max_length=512,padding=False)
    dataset=Dataset.from_list(train).map(tokenize,batched=True,remove_columns=["text"])
    settings=TrainingArguments(output_dir=str(output),num_train_epochs=1,
                              per_device_train_batch_size=1,gradient_accumulation_steps=8,
                              learning_rate=8e-5,logging_steps=20,save_strategy="epoch",
                              report_to="none",fp16=True)
    trainer=Trainer(model=model,args=settings,train_dataset=dataset,
                    data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer,mlm=False))
    trainer.train()
    model.save_pretrained(str(output/"candidate-adapter"))
    tokenizer.save_pretrained(str(output/"candidate-adapter"))
    (output/"HOLDOUT_REQUIRED.txt").write_text(
      "Adaptador candidato. Ejecutar evaluación ciega contra baseline y obtener "
      "aprobación humana antes de promoción. No activarlo automáticamente.\n")
    print("Candidato entrenado, no publicado. Ejemplos entrenamiento:",len(train),
          "reserva de evaluación:",len(_heldout))

if __name__=="__main__":
    main()
