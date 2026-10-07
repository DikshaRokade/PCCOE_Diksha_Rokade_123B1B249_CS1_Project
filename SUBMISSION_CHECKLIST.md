# Submission checklist (map of required artifacts to files)

| Required artifact | Where | Your action |
|---|---|---|
| Approved synopsis + faculty approval record | `Synopsis/Project_Synopsis_Diksha_123B1B249_CS1.docx` (+ PDF) | Print, tick both declaration boxes, sign, get faculty signature; scan into `Synopsis/` |
| Student declaration (signed) | `Declarations/Student_Declaration.docx` | Print and sign; scan |
| AI-tool usage + external dependency declarations | `Declarations/` | Review, sign |
| Source code, evaluation scripts, helper scripts | `Code/` | Read it so you can explain it |
| Input data / knowledge base | `Input_Data/` (synthetic PDFs + ground truth + DATA_CARD) | - |
| Model, prompts, config | `Model_Prompts_Config/` | Confirm the LLM tag you actually ran |
| Evaluation evidence | `Evaluation_Results/` | **Re-run with BGE + Ollama (see below)** |
| Technical report (PDF, synopsis format) | `Documentation/Technical_Report_Diksha_123B1B249_CS1.pdf` | Rebuild after the evaluation re-run; add your own contribution paragraph |
| Video (5-10 min) | `Video/` | Record using `VIDEO_SCRIPT_AND_CHECKLIST.md` |
| Final ZIP | folder name `PCCOE_<StudentName>_<PRN>_CS1_AIML.zip` | Zip after everything above |

## Before the deadline (in order)
1. `pip install -r Code/requirements.txt`, install Ollama, `ollama pull qwen2.5:7b-instruct`.
2. `python -m pytest Code/tests -q` - must pass.
3. `python Code/evaluation/evaluate.py --embedder bge --llm ollama` then `python Code/scripts/build_report.py`. Open the report: the yellow "fallback configuration" note disappears and the numbers are the real ones. If a metric is lower than before, report it as it is and update the failure analysis.
4. Start API + UI, run the demo questions once to be sure the demo works.
5. Record the video; sign and scan documents; add your full name to the folder name, the synopsis (Student Name) and the report cover if needed; zip.
