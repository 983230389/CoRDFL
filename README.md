# CoRDFL: Continuous Reflective Debugging for Fault Localization

This repository provides the implementation and experimental artifacts for of our work, which proposes a **Continuous Reflective Debugging for Fault Localization method (CoRDFL)**.

The goal of this project is to enhance fault localization performance by iteratively leveraging execution feedback from generated patches.

---

## 📌 Overview

CoRDFL introduces an iterative process:

> Localization → Patch Generation → Patch Execution → Reflection

In each iteration, the model refines its localization results based on feedback from patch execution, enabling progressive improvement in fault localization accuracy.

---

## 📂 Repository Structure

The repository is organized as follows:

 ├── ablation/                 # Results of ablation studies
 ├── code/                     # Core implementation of CoRDFL 
 ├── sourceofCodeContext/      # Source code context used for experiments
 ├── report/                   # Iterative experiment outputs and logs

### 📁 `ablation/`
Contains experimental results for different ablation settings, including:
- w/o Reflection Feedback
- w/o Execution Outcome Feedback
- w/o Multi-location Patch Exploration
- w/o Code-aware Reflection Context

These results are used to analyze the contribution of each component in CoRDFL.

---

### 📁 `code/`
Includes the main implementation of the CoRDFL framework:
- LLM-based fault localization pipeline
- Patch generation and execution scripts
- Multi-round reflection mechanism
- Interaction and prompt construction logic

---

### 📁 `sourceofCodeContext/`
Provides the source code context extracted from the benchmark:
- Function-level code snippets
- Contextual information used as model input
- Structured data derived from Defects4J

---

### 📁 `report/`
Stores intermediate and final results generated during iterative experiments:
- Per-round localization outputs
- Ranking changes across iterations

This directory is essential for analyzing the behavior of the multi-round process.

---

## ⚙️ Experimental Setup

- Dataset: Defects4J v3.0.1
- Task: Statement-level fault localization
- Input:
  - Faulty function code
  - Failing test cases
  - Error logs
- Output:
  - Ranked suspicious statements

---

## 🔍 Key Features

- Integration of dynamic execution information
- Patch-based feedback for localization refinement
- Multi-round interaction with reflection
- Support for ablation studies

---

## 📊 Main Findings

- Dynamic execution information improves localization performance
- Multi-round reflection further enhances Top-1 accuracy
- Different components contribute differently to the final performance

---

## 📬 Notes

This repository is intended for research purposes.  
The experimental pipeline involves multiple iterations and external LLM calls.

---

## 📖 Citation

If you find this work useful, please cite our paper (to be added).