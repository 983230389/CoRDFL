import os
import pickle
import subprocess
import shutil
import time

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

FINAL_ROOT_PATH = "changeYourPath/final"

def _get_output_root_base(kind):
    return os.path.join(FINAL_ROOT_PATH, kind)

def _get_patch_root_path():
    return _get_output_root_base("patch")

def deal(experiment_id="4omini2", iteration_id="1", top_k_patches=5):
    # Base paths
    patch_root_path = _get_patch_root_path()
    data_root_path = "changeYourPath/data"
    
    current_patch_path = os.path.join(patch_root_path, experiment_id, iteration_id)
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Iter {iteration_id}] Stage: Patch Execution")

    # Iterate through projects and versions
    for projectName in projectOrigin.keys():
        for versionInt in range(1, projectOrigin[projectName] + 1):
            versionStr = str(versionInt) + "b"
            
            print(f"[{time.strftime('%H:%M:%S')}] [Iter {iteration_id}] PatchRun processing {projectName}-{versionStr}")

            # Skip logic matching previous scripts
            if projectName == "Closure" and versionStr in ["34b", "68b", "123b", "132b", "157b", "173b"]:
                continue
                
            project_patch_dir = os.path.join(current_patch_path, projectName, versionStr)
            if not os.path.exists(project_patch_dir):
                continue
                
            # Path to the checked-out project source code
            # Assuming standard Defects4J structure in data_root_path
            # e.g., data/Chart/1b
            project_source_root = os.path.join(data_root_path, projectName, versionStr)
            
            if not os.path.exists(project_source_root):
                print(f"Source code not found for {projectName} {versionStr} at {project_source_root}")
                continue

            print(f"Processing {projectName} {versionStr}...")

            for rank in range(1, top_k_patches + 1):
                patch_file_base = f"top{rank}patch"
                dir_file_base = f"top{rank}Dir"
                
                patch_out_path = os.path.join(project_patch_dir, patch_file_base + ".out")
                dir_out_path = os.path.join(project_patch_dir, dir_file_base + ".out")
                
                if not os.path.exists(patch_out_path) or not os.path.exists(dir_out_path):
                    continue
                
                # Check if result already exists
                result_out_path = os.path.join(project_patch_dir, f"top{rank}out.out")
                if os.path.exists(result_out_path):
                    print(f"  Rank {rank} already processed.")
                    continue

                try:
                    # Load patch content
                    with open(patch_out_path, "rb") as f:
                        patch_code = pickle.load(f)
                    
                    # Load directory info
                    with open(dir_out_path, "rb") as f:
                        fault_info = pickle.load(f)
                        
                    line_number = fault_info.get("lineNumber")
                    fault_rel_path = fault_info.get("faultDir") # e.g., source/org/jfree/chart/renderer/category/AbstractCategoryItemRenderer
                    
                    if not fault_rel_path:
                        print(f"  Rank {rank}: Missing faultDir")
                        continue
                        
                    # Construct absolute path to the target java file
                    # We need to append ".java" if not present
                    if not fault_rel_path.endswith(".java"):
                        fault_rel_path += ".java"
                        
                    target_file_path = os.path.join(project_source_root, fault_rel_path)
                    
                    if not os.path.exists(target_file_path):
                        print(f"  Rank {rank}: Target file not found at {target_file_path}")
                        continue
                        
                    # --- APPLY PATCH ---
                    print(f"  Rank {rank}: Applying patch to {os.path.basename(target_file_path)}:{line_number}")
                    
                    # Backup original file
                    backup_path = target_file_path + ".bak"
                    shutil.copy2(target_file_path, backup_path)
                    
                    try:
                        with open(target_file_path, "r", encoding="utf-8", errors='ignore') as f:
                            lines = f.readlines()
                        
                        # Line numbers are 1-based, list index is 0-based
                        if line_number > len(lines) or line_number < 1:
                             print(f"  Rank {rank}: Line number {line_number} out of range")
                             # Restore and skip
                             shutil.move(backup_path, target_file_path)
                             continue

                        # Replace the line
                        # Note: patch_code might contain multiple lines or no newlines
                        # We replace lines[line_number-1] with patch_code + newline
                        
                        # Ensure patch ends with newline if not empty
                        if patch_code and not patch_code.endswith('\n'):
                            patch_code += '\n'
                            
                        lines[line_number - 1] = patch_code
                        
                        with open(target_file_path, "w", encoding="utf-8") as f:
                            f.writelines(lines)
                            
                        # --- RUN TESTS ---
                        print(f"  Rank {rank}: Running defects4j test...")
                        
                        # Run defects4j test in the project directory
                        # Capture stdout and stderr
                        try:
                            # Set timeout to avoid infinite loops (e.g. 5 minutes)
                            result = subprocess.run(
                                ["defects4j", "test"],
                                cwd=project_source_root,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=300 
                            )
                            output = result.stdout + "\n" + result.stderr
                        except subprocess.TimeoutExpired:
                            output = "Timeout: Test execution took longer than 5 minutes."
                        except Exception as e:
                            output = f"Error running tests: {str(e)}"
                            
                        # Save output
                        with open(result_out_path, "wb") as f:
                            pickle.dump(output, f)
                            
                        result_txt_path = os.path.join(project_patch_dir, f"top{rank}out.txt")
                        with open(result_txt_path, "w", encoding="utf-8") as f:
                            f.write(output)
                            
                        print(f"  Rank {rank}: Test completed.")

                    finally:
                        # --- RESTORE ORIGINAL FILE ---
                        if os.path.exists(backup_path):
                            shutil.move(backup_path, target_file_path)
                            # print(f"  Rank {rank}: Restored original file.")

                except Exception as e:
                    print(f"  Rank {rank}: Error processing patch: {e}")

if __name__ == "__main__":
    deal("4omini","2")
    deal("4omini","3")
