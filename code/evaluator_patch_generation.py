import json
import os
import pickle
import re
import time
import http.client
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

def call_llm_retry(model, messages):
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
                "messages": messages
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

def _get_report_root_path(experiment_id, iteration_id):
    return os.path.join(_get_output_root_base("report"), experiment_id, iteration_id)

def _get_patch_root_path(experiment_id, iteration_id):
    return os.path.join(_get_output_root_base("patch"), experiment_id, iteration_id)

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

def clean_json_string(s):
    # Try to find JSON block using regex
    # Match content between ```json and ``` or just ``` and ```
    # or look for the first { and last } if no code blocks found
    s = s.strip()
    
    # Pattern 1: ```json ... ``` or ``` ... ```
    # DOTALL flag lets . match newlines
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', s, re.DOTALL)
    if match:
        return match.group(1)
        
    # Pattern 2: No code blocks, just try to find the outer-most JSON object
    # Find first '{' and last '}'
    start = s.find('{')
    end = s.rfind('}')
    
    if start != -1 and end != -1 and end > start:
        return s[start:end+1]
        
    # Fallback: return original string (might fail, but worth a shot)
    return s

def clean_patch_content(s):
    # Remove markdown code block syntax if present in patch
    s = s.strip()
    # Regex to remove ```java, ```, etc.
    s = re.sub(r'^```\w*\n', '', s)
    s = re.sub(r'\n```$', '', s)
    return s.strip()

def deal(experiment_id="4omini1", iteration_id="1", top_k_locations=5):
    # Paths
    nl_info_root_path = "changeYourPath/sourceofCodeContext"
    
    report_root_path = _get_report_root_path(experiment_id, iteration_id)
    patch_root_path = _get_patch_root_path(experiment_id, iteration_id)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Iter {iteration_id}] Stage: Patch Generation")

    # We iterate through all projects
    for projectName in projectOrigin.keys():
        for versionInt in range(1, projectOrigin[projectName] + 1):
            versionStr = str(versionInt) + "b"
            
            print(f"[{time.strftime('%H:%M:%S')}] [Iter {iteration_id}] PatchGen processing {projectName}-{versionStr}")

            # Skip logic matching Actor script
            if projectName == "Closure" and versionStr in ["34b", "68b", "123b", "132b", "157b", "173b"]:
                continue

            # 1. Read NLInformation (for full function code)
            nl_info_path = os.path.join(nl_info_root_path, projectName, versionStr, "NLInformation.in")
            if not os.path.exists(nl_info_path):
                continue
            
            try:
                with open(nl_info_path, "rb") as f:
                    nl_data_list = pickle.load(f)
                    # Assuming we process the first item as in Actor script
                    if not nl_data_list:
                        continue
                    nl_item = nl_data_list[0]
            except Exception as e:
                print(f"Error reading NLInfo for {projectName} {versionStr}: {e}")
                continue

            # 2. Read Actor Report
            report_path = os.path.join(report_root_path, projectName, versionStr, "gpt4ominiAnswer.out")
            if not os.path.exists(report_path):
                print(f"Report not found for {projectName} {versionStr}")
                continue

            try:
                with open(report_path, "rb") as f:
                    actor_results = pickle.load(f)
                    if not actor_results:
                        continue
                    # Actor result structure: [{'result': 'JSON_STRING'}]
                    # Or [{'answer1': ..., 'answer2': ..., 'result': ...}]
                    # We look for 'result'
                    actor_result_str = actor_results[0].get('result', '')
                    if not actor_result_str:
                        print(f"No result in report for {projectName} {versionStr}")
                        continue
                    
                    json_str = clean_json_string(actor_result_str)
                    actor_data = json.loads(json_str)
                    fault_locations = actor_data.get('faultLocalization', [])
            except Exception as e:
                print(f"Error parsing report for {projectName} {versionStr}: {e}")
                # Log parsing failure
                with open("json_parse_errors.log", "a") as log_file:
                    log_file.write(f"{projectName} {versionStr}: {str(e)}\n")
                continue

            if ABLATION_VARIANT == "WO_MULTI_LOCATION_PATCH_EXPLORATION":
                top_k_locations = 1

            # 3. Generate Patches for top locations
            output_dir = os.path.join(patch_root_path, projectName, versionStr)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            print(f"Processing {projectName} {versionStr} - Found {len(fault_locations)} locations")

            # Construct full function code for context
            full_code = ""
            for i in range(len(nl_item["faultLineNumbers"])):
                full_code += f"{nl_item['faultLineContent'][i]}\n"

            for idx, location in enumerate(fault_locations[:top_k_locations]):
                rank = idx + 1
                target_file_base = f"top{rank}patch"
                out_path = os.path.join(output_dir, target_file_base + ".out")
                txt_path = os.path.join(output_dir, target_file_base + ".txt")

                # Skip if already exists (checkpointing)
                if os.path.exists(out_path):
                    continue

                line_number = location.get('lineNumber')
                code_content = location.get('codeContent')
                reason = location.get('reason')

                prompt = f"""You are an expert Java developer. I will provide you with a buggy function and a specific location suspected of having a bug.
Your task is to generate a patch (correct code) to fix the bug at that location.

Buggy Function:
{full_code}

Suspicious Location:
Code: {code_content}
Reason for Suspicion: {reason}

Please provide ONLY the fixed code snippet that should replace the suspicious line(s). 
- Do not include any explanation.
- Do not include markdown formatting (like ```java).
- If multiple lines need to be replaced or added, provide the complete block.
- The output should be ready to be swapped into the code.
"""

                messages = [
                    {"role": "system", "content": "You are a coding assistant that outputs only code patches."},
                    {"role": "user", "content": prompt}
                ]

                try:
                    res = call_llm_retry(model_name, messages)
                    patch_content = res.choices[0].message.content
                    patch_content = clean_patch_content(patch_content)
                    
                    # Write to files
                    # .out stores the string object
                    with open(out_path, "wb") as f:
                        pickle.dump(patch_content, f)
                    
                    # .txt stores the string text
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(patch_content)
                    
                    # Store faultDir info
                    dir_out_path = os.path.join(output_dir, f"top{rank}Dir.out")
                    dir_txt_path = os.path.join(output_dir, f"top{rank}Dir.txt")
                    
                    # Construct fault info object: {lineNumber, faultDir}
                    # Note: We need to retrieve faultDir from nl_item. 
                    # nl_item["faultDir"] should contain the path to the buggy file.
                    fault_info = {
                        "lineNumber": line_number,
                        "faultDir": nl_item.get("faultDir", "") 
                    }
                    
                    with open(dir_out_path, "wb") as f:
                        pickle.dump(fault_info, f)
                        
                    with open(dir_txt_path, "w", encoding="utf-8") as f:
                        f.write(str(fault_info))
                    
                    print(f"  Generated patch for rank {rank}")

                except Exception as e:
                    print(f"  Error generating patch for rank {rank}: {e}")

if __name__ == "__main__":
    deal("4omini","1")
