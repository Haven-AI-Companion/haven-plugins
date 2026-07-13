import sys
import os
import json
import uuid
import urllib.request
import time

def log_debug(msg):
    print(f"[3D Generator] {msg}", file=sys.stderr)

def main():
    try:
        # 1. Read stdin
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            log_debug("Error: No input arguments received.")
            return

        # 2. Parse JSON
        args = json.loads(raw_input)
        description = args.get("description", "").strip()
        if not description:
            log_debug("Error: Description argument is missing or empty.")
            return

        log_debug(f"Received description prompt: '{description}'")

        # 3. Read config and check for Tripo3D API Key
        config = args.get("config", {})
        tripo_api_key = config.get("tripo_api_key", "").strip()
        
        # Save output inside haven-server uploads folder
        uploads_dir = r"C:\Users\admin\haven-server\wwwroot\uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        filename = f"avatar_{uuid.uuid4().hex}.glb"
        filepath = os.path.join(uploads_dir, filename)

        model_url = None

        if tripo_api_key:
            log_debug("Tripo3D API key detected. Initiating custom text-to-3D generation task...")
            try:
                # API Call to Tripo3D to create text-to-model task
                task_url = "https://api.tripo3d.ai/v2/openapi/task"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {tripo_api_key}"
                }
                payload = {
                    "type": "text_to_model",
                    "prompt": f"high-quality rigged 3D character mesh, humanoid avatar style, {description}"
                }
                
                req = urllib.request.Request(
                    task_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                
                task_id = resp_data.get("data", {}).get("task_id")
                if not task_id:
                    log_debug(f"Failed to create task. Response: {resp_data}")
                    raise Exception("No task_id returned from Tripo3D")

                log_debug(f"Task created successfully. Task ID: {task_id}. Polling status...")

                # Poll task status
                status = "queued"
                poll_url = f"https://api.tripo3d.ai/v2/openapi/task/{task_id}"
                polls = 0
                max_polls = 40 # 200 seconds max
                
                while status in ["queued", "running"] and polls < max_polls:
                    time.sleep(5)
                    polls += 1
                    
                    poll_req = urllib.request.Request(poll_url, headers={"Authorization": f"Bearer {tripo_api_key}"})
                    with urllib.request.urlopen(poll_req, timeout=15) as poll_resp:
                        poll_data = json.loads(poll_resp.read().decode("utf-8"))
                    
                    status = poll_data.get("data", {}).get("status", "failed")
                    progress = poll_data.get("data", {}).get("progress", 0)
                    log_debug(f"Poll #{polls}: status = {status}, progress = {progress}%")
                    
                    if status == "success":
                        model_url = poll_data.get("data", {}).get("output", {}).get("model")
                        break
                    elif status == "failed":
                        log_debug(f"Tripo3D task failed. Error: {poll_data}")
                        break
                
            except Exception as e:
                log_debug(f"Tripo3D API failed or timed out: {e}.")

        # 4. Local generation using stable-diffusion.cpp + TripoSR
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            log_debug("Tripo3D API was not used or failed. Initiating local CPU generation...")
            try:
                # 4.1 Generate a 2D image via local sd-server (stable-diffusion-cpp)
                sd_server_url = config.get("sd_server_url", "http://127.0.0.1:8080").strip()
                sd_url = f"{sd_server_url.rstrip('/')}/v1/images/generations"
                
                log_debug(f"Querying local SD server at: {sd_url} to generate 2D reference portrait...")
                
                import random
                seed_val = random.randint(1, 2000000000)
                full_prompt = f"digital art portrait, highly detailed, {description}<sd_cpp_extra_args>{{\"seed\": {seed_val}}}</sd_cpp_extra_args>"
                
                payload = {
                    "prompt": full_prompt,
                    "negative_prompt": "text, watermark, bad anatomy, duplicate, split screen, multi panel, list, borders, signature, extra limbs",
                    "n": 1,
                    "size": "512x512",
                    "seed": seed_val,
                    "response_format": "b64_json"
                }
                
                req = urllib.request.Request(
                    sd_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                
                with urllib.request.urlopen(req, timeout=120) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    
                data_list = resp_data.get("data", [])
                if not data_list:
                    raise Exception("No image data returned from local SD server")
                    
                b64_string = data_list[0].get("b64_json", "")
                if not b64_string:
                    raise Exception("Empty b64_json returned from local SD server")
                
                import base64
                image_bytes = base64.b64decode(b64_string)
                
                # Save the 2D image temporarily to uploads/temp_portrait_<uuid>.png
                temp_img_name = f"temp_portrait_{uuid.uuid4().hex}.png"
                temp_img_path = os.path.join(uploads_dir, temp_img_name)
                
                with open(temp_img_path, "wb") as f_img:
                    f_img.write(image_bytes)
                
                log_debug(f"Temporary reference image saved to: {temp_img_path}")
                
                # 4.2 Run TripoSR in virtual environment
                python_exe = r"C:\Users\admin\triposr-env\Scripts\python.exe"
                triposr_script = r"C:\Users\admin\triposr-src\run.py"
                temp_out_dir = os.path.join(r"C:\Users\admin\triposr-src", f"output_{uuid.uuid4().hex}")
                
                import subprocess
                import shutil
                
                # Invoke TripoSR
                cmd = [
                    python_exe,
                    triposr_script,
                    temp_img_path,
                    "--device", "cpu",
                    "--model-save-format", "glb",
                    "--output-dir", temp_out_dir
                ]
                
                log_debug(f"Executing local TripoSR: {' '.join(cmd)}")
                
                process = subprocess.run(
                    cmd,
                    cwd=r"C:\Users\admin\triposr-src",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=180
                )
                
                if process.stderr:
                    log_debug(f"TripoSR stderr:\n{process.stderr}")
                
                # Check for output GLB
                local_glb = os.path.join(temp_out_dir, "0", "mesh.glb")
                if os.path.exists(local_glb) and os.path.getsize(local_glb) > 0:
                    shutil.copy2(local_glb, filepath)
                    log_debug(f"Local 3D model generated and copied to: {filepath}")
                else:
                    raise Exception(f"TripoSR did not output mesh.glb. Exit code: {process.returncode}")
                
                # Cleanup temp directories and files
                try:
                    if os.path.exists(temp_img_path):
                        os.remove(temp_img_path)
                    if os.path.exists(temp_out_dir):
                        shutil.rmtree(temp_out_dir)
                except Exception as cleanup_err:
                    log_debug(f"Warning: Cleanup failed: {cleanup_err}")
                    
            except Exception as local_err:
                log_debug(f"Local 3D generation failed: {local_err}. Falling back to preset models...")

        # 5. Fallback: Curated dynamic presets if local CPU generation also failed/skipped
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            log_debug("Executing dynamic keyword matching for fallback avatar models...")
            desc_lower = description.lower()
            
            # Map descriptive prompts to beautiful open-source base characters
            if any(k in desc_lower for k in ["robot", "android", "cyborg", "futuristic", "sci-fi"]):
                log_debug("Keyword Match: Android/Cyborg model")
                model_url = "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CesiumMan/glTF-Binary/CesiumMan.glb"
            elif any(k in desc_lower for k in ["female", "girl", "woman", "wife", "she"]):
                log_debug("Keyword Match: Female Humanoid VRoid model")
                model_url = "https://raw.githubusercontent.com/vrm-c/UniVRM/master/Tests/Models/Alicia_vrm-0.51/AliciaSolid_vrm-0.51.vrm"
            elif any(k in desc_lower for k in ["male", "boy", "man", "husband", "he"]):
                log_debug("Keyword Match: Male Humanoid model")
                model_url = "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/RiggedFigure/glTF-Binary/RiggedFigure.glb"
            elif any(k in desc_lower for k in ["knight", "armor", "sword", "warrior"]):
                log_debug("Keyword Match: Knight/Warrior model")
                model_url = "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CesiumMan/glTF-Binary/CesiumMan.glb"
            else:
                log_debug("No explicit keyword match. Defaulting to standard companion avatar...")
                model_url = "https://raw.githubusercontent.com/vrm-c/UniVRM/master/Tests/Models/Alicia_vrm-0.51/AliciaSolid_vrm-0.51.vrm"

            # Download the fallback model file
            log_debug(f"Downloading model from: {model_url}")
            try:
                req = urllib.request.Request(
                    model_url, 
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=60) as response:
                    model_bytes = response.read()

                with open(filepath, "wb") as f:
                    f.write(model_bytes)
            except Exception as dl_err:
                log_debug(f"Failed to download preset fallback model: {dl_err}")

        # 6. Verify and output relative path to stdout
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            log_debug(f"Model saved successfully to {filepath} ({os.path.getsize(filepath)} bytes).")
            # Print ONLY the relative URL path to stdout
            print(f"/uploads/{filename}")
        else:
            log_debug("Error: Output model was not created or empty.")

    except Exception as e:
        print(f"Error executing generate_3d_avatar: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    main()
