import openai
import json
from openai import OpenAI
import os
import pickle

import time

# Configuration
client = OpenAI(
    base_url="your_url",
    api_key="your_api",
    timeout=120
)

def call_llm_retry(model, messages):
    while True:
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages
            )
        except Exception as e:
            print(f"API call failed: {e}. Retrying...")
            time.sleep(2)


model_name = "your_model_name"
FINAL_ROOT_PATH = "changeYourPath/final"

def _get_output_root_base(kind):
    return os.path.join(FINAL_ROOT_PATH, kind)

def _get_report_root_path(experiment_id, iteration_id):
    return os.path.join(FINAL_ROOT_PATH, "report", experiment_id, iteration_id)

projectOrigin = {
    "Chart": 26,
    "Lang": 65,
    "Math": 106,
    "Mockito": 38,
    "Time": 27,
    "Closure": 176,
    "Cli": 39,
    "Codec": 18,
    "Collections": 4,
    "Compress": 47,
    "Csv": 16,
    "Gson": 18,
    "JacksonCore": 26,
    "JacksonDatabind": 112,
    "JacksonXml": 6,
    "Jsoup": 93,
    "JxPath": 22,
}

def deal(experiment_id="experiment_id", iteration_id="iteration_id", use_reflection_feedback=True):
    # Update paths for the current environment
    readFileRootPath = "changeYourPath/sourceofCodeContext"
    reflectionRootPath = _get_output_root_base("reflection")
    
    outputFileRootPath = _get_report_root_path(experiment_id, iteration_id)

    # Only run once for the initial report
    for repeatTime in [0]:
        for projectName in projectOrigin.keys():
            for versionInt in range(1, projectOrigin[projectName] + 1):
                versionStr = str(versionInt) + "b"

                # Skip logic from original script
                if projectName == "Closure" and versionStr in ["34b", "68b", "123b", "132b", "157b", "173b"]:
                    continue

                readFilePath = os.path.join(readFileRootPath, projectName, versionStr, "NLInformation.in")
                if not os.path.exists(readFilePath):
                    continue
                
                try:
                    with open(readFilePath, "rb") as file:
                        questions = pickle.load(file)
                except Exception as e:
                    print(f"Error reading {readFilePath}: {e}")
                    continue

                # Output directory: report/{project}/{version}
                outputDirPath = os.path.join(outputFileRootPath, projectName, versionStr)
                if not os.path.exists(outputDirPath):
                    os.makedirs(outputDirPath)

                # Output file names
                if repeatTime == 0:
                    outputFilePath = os.path.join(outputDirPath, "gpt4ominiAnswer.out")
                    outputTxtPath = os.path.join(outputDirPath, "gpt4ominiAnswer.txt")
                else:
                    outputFilePath = os.path.join(outputDirPath, "gpt4ominiAnswer_" + str(repeatTime) + ".out")
                    outputTxtPath = os.path.join(outputDirPath, "gpt4ominiAnswer_" + str(repeatTime) + ".txt")

                answerList = []
                if os.path.exists(outputFilePath):
                    try:
                        answerList = pickle.load(open(outputFilePath, "rb"))
                    except:
                        answerList = []

                itemindex = -1
                while itemindex < len(questions):
                    itemindex += 1
                    if itemindex >= len(questions):
                        break

                    if len(answerList) > itemindex:
                        continue
                    
                    item = questions[itemindex]
                    print(repeatTime, projectName, versionStr, itemindex, "start")

                    if len(item["faultLineContent"]) < 2:
                        print("too short")
                        answerList.append({})
                        continue

                    singleAnswerResult = {}

                    # Check if Prompt 2 will run (Error Log Analysis)
                    testCaseNum = -1
                    if len(item["errorLogContent"]) > 0:
                        for testCaseIndex in range(len(item["testCaseLineNum"])):
                            if len(item["testCaseContent"][testCaseIndex]) > 0 and len(
                                    item["errorLogContent"][testCaseIndex]) > 0:
                                testCaseNum = testCaseIndex
                                break
                    
                    will_run_prompt2 = (testCaseNum != -1)

                    # --- Prompt 1: Code Analysis ---
                    prompt1 = "Please analyze the following code snippet for potential bugs. Return the results in " \
                              "JSON format, consisting of a single JSON object with two fields: " \
                              "'intentOfThisFunction' (describing the intended purpose of the function)," \
                              "and 'faultLocalization' (an array of JSON objects). The 'faultLocalization' array " \
                              "should contain up to five JSON objects, each with three fields: 'lineNumber' (" \
                              "indicating the line number of the suspicious code)," \
                              "'codeContent' (showing the actual code), and 'reason' (explaining why this location is " \
                              "identified as potentially buggy). Note: The codes in the 'faultLocalization' array " \
                              "should be listed in descending order of suspicion.\n\n"
                    
                    prompt1 += "Code Snippet:\n"
                    for line in range(len(item["faultLineNumbers"])):
                        # Added "\n" for better formatting compared to original script
                        prompt1 += str(item["faultLineNumbers"][line]) + ":" + item["faultLineContent"][line].strip() + "\n"

                    # Iterative Reflection Logic
                    reflection_msg = ""
                    if use_reflection_feedback and int(iteration_id) > 1:
                        try:
                            # Path to previous iteration's reflection
                            prev_iteration = str(int(iteration_id) - 1)
                            reflection_path = os.path.join(reflectionRootPath, experiment_id, prev_iteration, projectName, versionStr, "reflection.out")
                            
                            if os.path.exists(reflection_path):
                                with open(reflection_path, "rb") as f:
                                    reflection_content = pickle.load(f)
                                reflection_msg = f"\n\nYou are in the {iteration_id}th iteration. Here is the reflection from the previous iteration:\n\n{reflection_content}\n\nBased on this reflection, please refine your analysis and provide the fault localization."
                            else:
                                # If reflection is missing, we proceed without it (or you could choose to skip)
                                print(f"Warning: Reflection file not found for {projectName} {versionStr} at {reflection_path}")
                        except Exception as e:
                            print(f"Error reading reflection: {e}")
                    
                    # If NOT running Prompt 2, append reflection to Prompt 1
                    if not will_run_prompt2 and reflection_msg:
                        prompt1 += reflection_msg

                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt1}
                    ]

                    try:
                        res = call_llm_retry(model_name, messages)
                        answer1 = res.choices[0].message.content
                        
                        # We need to maintain context for Prompt 2
                        messages.append({"role": "assistant", "content": answer1})
                        
                        final_result = answer1 # Default to answer1 if no log
                    except Exception as e:
                        print(f"Error in API call 1: {e}")
                        answerList.append({})
                        continue

                    # --- Prompt 2: Error Log & Test Case Analysis ---
                    if will_run_prompt2:
                        prompt2 = "I have received an error message and a unit test case related to the code snippet " \
                                  "I provided in the first prompt. The error message is: \""
                        
                        # testCaseNum is already calculated
                        temp1 = ""
                        for line in range(len(item["errorLogContent"][testCaseNum])):
                            if line > 0 and "---" in item["errorLogContent"][testCaseNum][line]:
                                break
                            temp1 += item["errorLogContent"][testCaseNum][line].strip() + "\n"

                        prompt2 += temp1[:3000]
                        prompt2 += "\". Additionally, here is the unit test case: \""
                        testCases = ""
                        for line in range(len(item["testCaseLineNum"][testCaseNum])):
                            testCases += str(item["testCaseLineNum"][testCaseNum][line]) + ":" + \
                                            item["testCaseContent"][testCaseNum][line].strip() + "\n"

                        prompt2 += testCases[:1000]
                        
                        # Add reflection here if available
                        if reflection_msg:
                            prompt2 += reflection_msg
                        
                        prompt2 += "\". Please analyze the parts contained in <code> and </code> from the first prompt, along with the " \
                                   "provided error message and unit test case." \
                                   "Update and return the JSON object consisting of 'intentOfThisFunction' (" \
                                   "describing the intended purpose of the function)," \
                                   "and 'faultLocalization' (an array of JSON objects). The 'faultLocalization' " \
                                   "array should contain up to five JSON objects, each with three fields: 'lineNumber' (" \
                                   "indicating the line number of the suspicious code)," \
                                   "'codeContent' (showing the actual code), and 'reason' (explaining why this " \
                                   "location is identified as potentially buggy)." \
                                   "Note: The codes in the 'faultLocalization' array should be listed in " \
                                   "descending order of suspicion, and the analysis should focus exclusively on " \
                                   "the code snippet from the first prompt and not the unit test case."
                        
                        message = {"role": "user", "content": prompt2}
                        messages.append(message)

                        try:
                            resLog = call_llm_retry(model_name, messages)
                            final_result = resLog.choices[0].message.content
                        except Exception as e:
                            print(f"Error in API call 2: {e}")
                            # If 2nd call fails, keep 1st result
                            pass

                    # Save only the final result as requested
                    singleAnswerResult["result"] = final_result
                    answerList.append(singleAnswerResult)

                    # Write to file immediately (checkpointing)
                    with open(outputFilePath, "wb") as file:
                        pickle.dump(answerList, file)
                    with open(outputTxtPath, "w", encoding="utf-8") as file:
                        file.write(str(answerList))

if __name__ == "__main__":
    deal()
