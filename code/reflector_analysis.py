import json
import os
import pickle
import time
import http.client
import re
from urllib.parse import urlparse

# Mock classes to maintain compatibility with existing code
class MockMessage:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

def call_llm_retry(model, messages, temperature=0.1):
    # Configuration
    api_key = "your_api"
    base_url = "your_url"
    
    parsed_url = urlparse(base_url)
    hostname = parsed_url.netloc
    path = parsed_url.path + "/chat/completions"

    while True:
        try:
            conn = http.client.HTTPSConnection(hostname, timeout=120)
            
            payload = json.dumps({
                "model": model,
                "messages": messages,
                "temperature": temperature
            })
            
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            conn.request("POST", path, payload, headers)
            res = conn.getresponse()
            data = res.read()
            
            if res.status != 200:
                print(f"HTTP Error {res.status}: {data.decode('utf-8')}")
                raise Exception(f"HTTP Error {res.status}")
                
            response_json = json.loads(data.decode("utf-8"))
            content = response_json["choices"][0]["message"]["content"]
            return MockResponse(content)
            
        except Exception as e:
            print(f"API call failed: {e}. Retrying...")
            time.sleep(2)


model_name = "your_model_name"
FINAL_ROOT_PATH = "changeYourPath/final"

def _get_output_root_base(kind):
    return os.path.join(FINAL_ROOT_PATH, kind)

def _get_patch_root_path():
    return os.path.join(FINAL_ROOT_PATH, "patch")

def _get_reflection_root_path():
    return _get_output_root_base("reflection")

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

def _summarize_exec_output(test_output: str) -> str:
    if not test_output:
        return "No test output."
    output = str(test_output)
    status = "unknown"
    if "BUILD FAILED" in output or "Compilation failed" in output:
        status = "compile_failed"
    elif "[javac]" in output and "error:" in output:
        status = "compile_failed"
    elif "Failing tests:" in output:
        status = "tests_failed"
    elif "Failing tests: 0" in output or "Failing tests: 0" in output:
        status = "tests_passed"
    m = re.search(r"Failing tests:\s*(\d+)", output)
    failing_count = m.group(1) if m else ""
    lines = [ln.rstrip() for ln in output.splitlines() if ln.strip()]
    head = "\n".join(lines[:12])
    tail = "\n".join(lines[-12:]) if len(lines) > 12 else ""
    summary = f"Status: {status}"
    if failing_count:
        summary += f"\nFailing tests: {failing_count}"
    if head:
        summary += f"\n\nTop:\n{head}"
    if tail and tail != head:
        summary += f"\n\nBottom:\n{tail}"
    return summary[:1200]


def process_single_project(
    projectName,
    versionStr,
    current_patch_path,
    current_reflection_path,
    nl_info_root_path,
    patch_topk=5,
    include_execution_outcome=True,
    include_code_context=True,
    include_patch_code=True,
):
    # Skip logic
    if projectName == "Closure" and versionStr in ["34b", "68b", "123b", "132b", "157b", "173b"]:
        return
        
    project_patch_dir = os.path.join(current_patch_path, projectName, versionStr)
    if not os.path.exists(project_patch_dir):
        return
    
    # Check if reflection already exists (Breakpoint Resume)
    project_reflection_dir = os.path.join(current_reflection_path, projectName, versionStr)
    reflection_out_file = os.path.join(project_reflection_dir, "reflection.out")
    if os.path.exists(reflection_out_file):
        print(f"Skipping {projectName} {versionStr}: Reflection already exists.")
        return
        
    print(f"Generating reflection for {projectName} {versionStr}...")
    
    # Load NLInformation to get original code context
    nl_info_path = os.path.join(nl_info_root_path, projectName, versionStr, "NLInformation.in")
    nl_info_data = []
    if os.path.exists(nl_info_path):
        try:
            with open(nl_info_path, "rb") as f:
                nl_info_data = pickle.load(f)
        except Exception as e:
            print(f"  Error loading NLInformation: {e}")

    

    # Collect info from patch attempts
    patch_results_summary = ""
    found_any_result = False
    attempt_count = 0
    
    for rank in range(1, patch_topk + 1):
        # Check for patch code, dir info, and test output
        patch_file = os.path.join(project_patch_dir, f"top{rank}patch.out")
        dir_file = os.path.join(project_patch_dir, f"top{rank}Dir.out")
        out_file = os.path.join(project_patch_dir, f"top{rank}out.out") # Changed to .out for consistency
        
        if not (os.path.exists(patch_file) and os.path.exists(dir_file) and os.path.exists(out_file)):
            continue
        
        found_any_result = True
        attempt_count += 1
        
        # Load Data
        try:
            with open(patch_file, "rb") as f:
                patch_code = pickle.load(f)
            with open(dir_file, "rb") as f:
                fault_info = pickle.load(f)
                line_number = fault_info.get("lineNumber")
            # Use pickle to load the output string directly
            with open(out_file, "rb") as f:
                test_output = pickle.load(f)
        except Exception as e:
            print(f"  Error loading files for Rank {rank}: {e}")
            continue

        # Find original code context from NLInformation
        original_code_context = "Not available"
        fault_line_content = "Not available"
        
        if include_code_context and nl_info_data:
            for func_info in nl_info_data:
                # Assuming faultLineNumbers is a list of integers or a string range we need to parse?
                # Based on previous context, faultLineNumbers might be a list of ints.
                # We check if line_number is in this function's range or specifically listed.
                # Simple heuristic: check if line_number matches any in the list or range
                # Let's try to match by exact line number if possible, or just dump the first matching function context
                
                # In NLInformation, faultLineNumbers is typically a list of line numbers [120, 121, ...]
                # But wait, fault_info from topRankDir.out has "lineNumber" (int).
                
                # Let's check if line_number is in func_info["faultLineNumbers"]
                # We need to handle potential format differences (list vs string)
                fl_nums = func_info.get("faultLineNumbers", [])
                if isinstance(fl_nums, str):
                    # Parse string "120-148" or similar if needed, but usually it's list in .in
                    pass 
                elif isinstance(fl_nums, list):
                     if line_number in fl_nums:
                         original_code_context = func_info.get("faultContext", "Not available")
                         # Try to find specific line content
                         # faultLineContent is often a list corresponding to faultLineNumbers? 
                         # Or just the whole function body?
                         # Let's assume faultContext is the full function code.
                         
                         # If faultLineContent is available and is a list corresponding to numbers
                         fl_content = func_info.get("faultLineContent", [])
                         if isinstance(fl_content, list) and len(fl_content) == len(fl_nums):
                             try:
                                 idx = fl_nums.index(line_number)
                                 fault_line_content = fl_content[idx]
                             except:
                                 pass
                         elif isinstance(fl_content, str):
                             fault_line_content = fl_content
                         
                         break

        exec_summary = ""
        if include_execution_outcome:
            if include_code_context or include_patch_code:
                truncated_output = test_output[:2000]
                if len(test_output) > 2000:
                    truncated_output += "\n...[Output Truncated]..."
                exec_summary = truncated_output
            else:
                exec_summary = _summarize_exec_output(test_output)
        
        patch_results_summary += f"""
--- Patch Attempt #{rank} ---
Location: Line {line_number}
"""
        if include_code_context:
            patch_results_summary += f"""
Original Code (Line {line_number}):
{fault_line_content}

Function Context:
{original_code_context}
"""
        if include_patch_code:
            patch_results_summary += f"""
Patch Code:
{patch_code}
"""
        if include_execution_outcome:
            patch_results_summary += f"""
Execution Feedback:
{exec_summary}
"""

    if not found_any_result:
        print(f"  No patch results found for {projectName} {versionStr}")
        return

    # Construct Prompt for Reflection
    prompt = f"""
You are a software debugging expert. We attempted to fix a bug in project {projectName} (version {versionStr}) using {attempt_count} patch attempt(s). The attempts may fail or pass.

Here is the summary of the patch attempts:

{patch_results_summary}

Please analyze these results and provide a "Reflection" for the next debugging iteration.

Your response MUST follow this exact format:

Analysis:
For each patch attempt, provide:
Patch #<N>:
- Reflection: <Detailed analysis of why this patch failed or succeeded based on the provided information>

Summary: <Brief summary of whether the fault localization seems correct>

Hint: <A short, actionable hint for the next iteration, max 200 words>
"""

    # Call LLM
    try:
        response = call_llm_retry(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant for software debugging and fault localization."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        reflection_content = response.choices[0].message.content
        
        # Save Reflection
        project_reflection_dir = os.path.join(current_reflection_path, projectName, versionStr)
        os.makedirs(project_reflection_dir, exist_ok=True)
        
        reflection_file = os.path.join(project_reflection_dir, "reflection.txt")
        with open(reflection_file, "w", encoding="utf-8") as f:
            f.write(reflection_content)

        reflection_out_file = os.path.join(project_reflection_dir, "reflection.out")
        with open(reflection_out_file, "wb") as f:
            pickle.dump(reflection_content, f)
            
        print(f"  Reflection saved to {reflection_file} and {reflection_out_file}")
        
    except Exception as e:
        print(f"  Error calling LLM or saving reflection: {e}")

def deal(experiment_id="4omini1", iteration_id="1"):
    # Base paths
    patch_root_path = _get_patch_root_path()
    reflection_root_path = _get_reflection_root_path()
    nl_info_root_path = "changeYourPath/sourceofCodeContext"
    
    current_patch_path = os.path.join(patch_root_path, experiment_id, iteration_id)
    current_reflection_path = os.path.join(reflection_root_path, experiment_id, iteration_id)
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Iter {iteration_id}] Stage: Reflector Analysis")

    # Iterate through projects
    for projectName in projectOrigin.keys():
        for versionInt in range(1, projectOrigin[projectName] + 1):
            versionStr = str(versionInt) + "b"
            
            print(f"[{time.strftime('%H:%M:%S')}] [Iter {iteration_id}] Reflector processing {projectName}-{versionStr}")
            
            process_single_project(projectName, versionStr, current_patch_path, current_reflection_path, nl_info_root_path)

def test_single_project(projectName, versionStr):
    # Base paths
    patch_root_path = _get_patch_root_path()
    reflection_root_path = _get_reflection_root_path()
    nl_info_root_path = "changeYourPath/sourceofCodeContext"
    
    experiment_id = "4omini1"
    iteration_id = "1"
    
    current_patch_path = os.path.join(patch_root_path, experiment_id, iteration_id)
    current_reflection_path = os.path.join(reflection_root_path, experiment_id, iteration_id)
    
    print(f"--- Testing Single Project: {projectName} {versionStr} ---")
    process_single_project(projectName, versionStr, current_patch_path, current_reflection_path, nl_info_root_path)



if __name__ == "__main__":
    deal(experiment_id="4omini", iteration_id="1")